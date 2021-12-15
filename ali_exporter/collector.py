from dataclasses import dataclass
import json
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Union
from Tea.exceptions import UnretryableException, TeaException
from alibabacloud_tea_openapi.models import Config as aliConfig
from alibabacloud_credentials.client import Client as credClient
from alibabacloud_cms20190101.client import Client as cmsClient
from alibabacloud_cms20190101.models import DescribeMetricLastRequest
from alibabacloud_tag20180828.client import Client as tagClient
from alibabacloud_tag20180828.models import ListTagResourcesRequest, ListTagResourcesResponseBodyTagResources
from prometheus_client import Counter
from prometheus_client.core import GaugeMetricFamily, InfoMetricFamily
from .config import Config, MetricRule


logger = logging.getLogger(__name__)
# 请求指标计数器
requestCounter = Counter("cms_requests", "CMS Request Total", labelnames=["action"])
failedrequestCounter = Counter("cms_failed_requests", "CMS Failed Requests Total", labelnames=["action"])


class AliyunCollector:
    def __init__(self, config: Config):
        self.config = config
        self.cred_client = credClient()
        self.cms_client = cmsClient(
            aliConfig(
                credential=self.cred_client,
                endpoint=config.endpoint.metrics
            )
        )

    def _safe_name(self, name: str) -> str:
    # 将不合法字符转换为下环线，并合并多个下划线
        name = re.sub('[^a-zA-Z0-9:_]', '_', name)
        return re.sub('__+', '_', name)

    def _safe_label_name(self, name: str) -> str:
    # 将不合法字符转换为下环线，并合并多个下划线
        name = re.sub('[^a-zA-Z0-9_]', '_', name)
        return re.sub('__+', '_', name)

    def _to_snake_case(self, name: str) -> str:
    # 将驼峰命名法的指标转换为snake case
        return re.sub(r'([a-z0-9])([A-Z])', r'\g<1>_\g<2>', name).lower()

    def _get_label_keys(self, datapoint: Dict[str, Union[str, float]]) -> Iterable[str]:
    # 生成指标标签，从数据点(datapoint)中去除数值的键
        for key in datapoint:
            if key.lower() not in {
                'timestamp', 'maximum', 'minimum', 'average', 
                'value', 'sum', 'sumps', 'samplecount'
            }:
                yield key

    def _format_label_names(self, name_list: Iterable[str]) -> Iterable[str]:
        for name in name_list:
            yield self._safe_label_name(self._to_snake_case(name))

    def _extract_resource_id_from_arn(self, arn: str) -> str:
    # 从arn中分离资源id
    # arn例子: arn:acs:ecs:cn-beijing:1234567890:instance/i-abcdefghijk
        arn_list = arn.split(":")
        resource_id = arn_list[-1].split("/")
        resource_id = resource_id[-1]
        return resource_id

    def _query_metric(self, rule: MetricRule) -> Iterable[Dict]:
    # 根据配置生成查询参数并查询

        # api只支持utc时间
        now = datetime.now(timezone.utc)

        # 设置查询参数，使用字典形式传参
        # 注：当前版本api只支持group by的表达式(express)
        optional_params = dict()
        if rule.group_by:
            optional_params['express'] = json.dumps(
                dict(groupby=rule.group_by)
            )
        if rule.dimensions:
            optional_params['dimensions'] = json.dumps(rule.dimensions)
        if rule.period_seconds:
            optional_params['period'] = rule.period_seconds
        elif self.config.period_seconds:
            optional_params['period'] = self.config.period_seconds
        if rule.delay_seconds:
            end_time = now - rule.delay_seconds
        else:
            end_time = now - self.config.delay_seconds
        optional_params['end_time'] = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if rule.range_seconds:
            start_time = end_time - rule.range_seconds
            optional_params['start_time'] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif self.config.range_seconds:
            start_time = end_time - self.config.range_seconds
            optional_params['start_time'] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 记录请求指标
        with failedrequestCounter.labels(action="DescribeMetricLast").count_exceptions():
            # while用来处理分页，模拟do..while循环
            while True:
                # 构建请求
                req = DescribeMetricLastRequest(
                    namespace=rule.namespace,
                    metric_name=rule.metric_name,
                    **optional_params
                )
                logger.debug(f"Request params: {req.to_map()}")

                response = self.cms_client.describe_metric_last(req)
                if not response.body.success:
                    raise TeaException({
                        'code': response.body.code,
                        'message': response.body.message,
                        'data': response.body.to_map()
                    })
                requestCounter.labels(action="DescribeMetricLast").inc()
                logger.debug(f"Response body: {response.body.to_map()}")

                # 用来处理带分页的数据点，因为一个分页产生的数据点集合是一个列表，
                # 可以使用yield from将多个分页里面的数据点取出来用生成器变成一个可迭代对象，而无需使用额外的列表存储
                yield from json.loads(response.body.datapoints)
                if not response.body.next_token:
                    break
                else:
                    optional_params = {"next_token": response.body.next_token}

    def _query_resource_tag(self, rule: MetricRule) -> Iterable[ListTagResourcesResponseBodyTagResources]:
        if rule.tag_select is None:
            return

        optional_params = {}
        for region in rule.tag_select.regions:
            tag_client = tagClient(
                aliConfig(
                    credential=self.cred_client,
                    region_id=region
                )
            )
            while True:
                req = ListTagResourcesRequest(
                    region_id=region,
                    resource_arn=[
                        f"arn:acs:{rule.tag_select.resource_type_selection.service}:*:*:{rule.tag_select.resource_type_selection.resource_type}/*"
                    ],
                    page_size=500,
                    **optional_params
                )

                response = tag_client.list_tag_resources(req)
                requestCounter.labels(action="ListTagResources").inc()
                yield from response.body.tag_resources
                if not response.body.next_token:
                    break
                else:
                    optional_params = {"next_token": response.body.next_token}

    def metric_generate(self, rule: MetricRule) -> Iterable[Union[GaugeMetricFamily, InfoMetricFamily]]:
        formated_metric_name = self._safe_name(f"{rule.namespace.lower()}_{self._to_snake_case(rule.metric_name)}")
        resource_id_set = set()
        job_name = rule.namespace.lower()
        logger.info(f"Processing metrics: {formated_metric_name}")

        # 获取指标数据点，并解析数据点的标签
        try:
            datapoints = list(self._query_metric(rule))
            if not datapoints:
                return
            label_names = list(self._get_label_keys(datapoints[0]))
        except UnretryableException as e:
            logger.exception(f"不可恢复错误! Code: {e.code}")
            return
        except IndexError as e:
            logging.error(f"KeyError: {repr(e)}| Datapoints: {datapoints}| Rule: {rule}")
            return
        except TeaException as e:
            logger.error(e)
            return
        except Exception as e:
            logger.exception("其他异常")
            return

        # 处理返回的指标数据点
        # 从规则中提取可以统计方式并与返回的数据取交集，防止出现空指标与字典取出错误
        for statistic in set(rule.statistics) & set(datapoints[0].keys()):
            # 设置指标系列标签
            gauge = GaugeMetricFamily(
                f"{formated_metric_name}_{statistic.lower()}",
                documentation='',
                labels=self._format_label_names(label_names)
            )
            # 通过数据点生成指标，因为阿里云不同指标的统计方法也会不同，所以需要先确定数据点是否存在该统计方法的键再获取数据
            for datapoint in datapoints:
                if datapoint.get(statistic) is not None:
                    gauge.add_metric(
                        labels=[datapoint[key] for key in label_names], 
                        value=datapoint[statistic], 
                        timestamp=datapoint['timestamp'] / 1000 if self.config.set_timestamp and rule.set_timestamp else None
                    )
            yield gauge

        # 获取资源的标签信息，以便在查询中与指标联合
        info_metric = InfoMetricFamily(
            "acs_resource",
            documentation='Aliyun tag information for resources',
            labels=["job", "instance"]
        )
        try:
            for tag_resource in self._query_resource_tag(rule):
                if tag_resource.resource_arn in self.published_tag_resources_arn:
                    continue
                values = {
                    f"tag_{self._safe_label_name(tag.key)}": tag.value for tag in tag_resource.tags
                }
                values['arn'] = tag_resource.resource_arn
                values[
                    self._safe_label_name(self._to_snake_case(rule.tag_select.resource_id_dimension))
                ] = self._extract_resource_id_from_arn(tag_resource.resource_arn)

                info_metric.add_metric(
                    labels=[job_name, ""],
                    value=values
                )
                self.published_tag_resources_arn.add(tag_resource.resource_arn)
        except TeaException as e:
            logger.error(e)
            return
        yield info_metric

    def collect(self):
        self.published_tag_resources_arn = set()
        for rule in self.config.metrics:
            yield from self.metric_generate(rule)
