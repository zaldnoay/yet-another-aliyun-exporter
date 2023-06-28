# 阿里云监控 Exporter
通过阿里云监控API将云监控指标导出为Prometheus指标数据  

## 支持产品
支持的云服务可参考[云服务监控项](https://help.aliyun.com/document_detail/163515.html?spm=api-workbench.API%20Explorer.0.0.25381e0fj0Xn9g)  
支持获取标签的服务参考 [支持标签API的资源类型](https://help.aliyun.com/document_detail/172061.html?spm=api-workbench.API%20Document.0.0.25671e0fpCIWrC)

## 快速开始

### 环境需求

* Python >= 3.7.1
* poetry >= 1.0.0

### 初始化运行环境

``` bash
cd yet-another-aliyun-exporter
portry install --no-dev # 开发环境可以不使用--no-dev
```

### 定义云API凭据

Exporter使用阿里云SDK的默认凭据链查找可用凭据，目前支持三种种方式：
1. 环境变量
   
    使用`ALIBABA_CLOUD_ACCESS_KEY_ID`和`ALIBABA_CLOUD_ACCESS_KEY_SECRET`作为凭据
2. 配置文件

    读取`~/.alibabacloud/credentials.ini`配置文件作为凭据
3. 实例RAM角色

    如果定义了`ALIBABA_CLOUD_ECS_METADATA`环境变量且不为空，则使用变量中的值作为ECS RAM角色名称获取临时凭据

详细可参考[使用默认凭据链](https://github.com/aliyun/credentials-python/blob/master/README-CN.md#%E4%BD%BF%E7%94%A8%E9%BB%98%E8%AE%A4%E5%87%AD%E8%AF%81%E6%8F%90%E4%BE%9B%E9%93%BE)

### 配置云服务监控指标信息

``` yaml
endpoint: "metrics.cn-beijing.aliyuncs.com"

metrics:
- namespace: acs_ecs_dashboard
  metric_name: CPUUtilization
- namespace: acs_slb_dashboard
  metric_name: ActiveConnection
```

### 启动Exporter

``` bash
poetry run start --config exporter.yaml
```

## Docker运行

### 镜像

目前docker镜像托管在github镜像仓库中，可以从以下地址获取

* [ghcr.io/zaldnoay/yet-another-aliyun-exporter](https://github.com/zaldnoay/yet-another-aliyun-exporter/pkgs/container/yet-another-aliyun-exporter)

可用的tag

* `main`: git仓库主分支的快照
* `latest`: 最新发布版本
* `vX.Y.Z`: 指定X.Y.Z版本的镜像

### 运行

镜像默认暴露9107端口作为服务，配置文件放置在`/srv/ali-exporter/config/aliyun.yaml`，使用docker运行的时候可以将配置文件挂载到该目录。

```
docker run -p 9107 -v /path/on/host/config.yml:/srv/ali-exporter/config/aliyun.yaml ghcr.io/zaldnoay/yet-another-aliyun-exporter
```

## 安装到Kubernetes（helm)

TODO

## 配置详细

``` yaml
# API访问的端点
endpoint:
  metrics: metrics.cn-heyuan.aliyuncs.com
log_level: WARNING
delay_seconds: 60
period_seconds: 60
metrics:
- namespace: acs_ots_new
  metric_name: InstanceCount2xxNumber
- namespace: acs_ots_new
  metric_name: InstanceCount4xxNumber
  statistics:
    - Average
    - Maximum
    - Minimum
    - Sum
    - Sumps
- namespace: acs_mns_new
  metric_name: DelayMessages
  period_seconds: 300
# kafka
- namespace: acs_kafka
  metric_name: message_accumulation
# slb
- namespace: acs_slb_dashboard
  metric_name: InstanceActiveConnection
  tag_select:
    regions:
      - cn-beijing
      - us-east-1
      - eu-central-1
    resource_id_dimension: instanceId
    resource_type_selection:
      service: slb
      resource_type: instance
```

| 名称 | 是否可选 | 描述 |
| ---- | ---- | ---- |
| endpoint.metrics | 是 | 访问API指标接入的端点，参考 [调用方式](https://help.aliyun.com/document_detail/28616.html) |
| log_level | 是 | 日志等级，默认为`WARNING`。可选值参考 [Python logging](https://docs.python.org/3/library/logging.html#logging-levels)
| namespace | 否 | 云服务的命名空间，值参考[云服务监控项](https://help.aliyun.com/document_detail/163515.html) |
| metric_name | 否 | 云服务的监控项名称，值参考[云服务监控项](https://help.aliyun.com/document_detail/163515.html) |
| statistics | 是 | 云服务监控数据的统计方式，值参考[云服务监控项](https://help.aliyun.com/document_detail/163515.html) |
| tag_select | 是 | 配置需要标签的标签资源信息，可以用来合并字段查询 |
| regions | 否 | 需要查询标签资源的地区 |
| resource_id_dimension | 否 | 资源id的维度/标签，用来映射到指标的资源id标签值 |
| resource_type_selection.service | 否 | 标签API的云服务code，参考[支持标签API的资源类型](https://help.aliyun.com/document_detail/172061.htm)中的ARN service |
| resource_type_selection.resource_type | 否 | 标签API的资源类型，参考[支持标签API的资源类型](https://help.aliyun.com/document_detail/172061.htm)中的ARN ResourceType |
| period_seconds | 是 | 监控数据的统计周期值参考[云服务监控项](https://help.aliyun.com/document_detail/163515.html)中的Period，可全局设置 |
| delay_seconds | 是 | 时间偏移量, 结束时间=now-delay_seconds，用来避免指标数据未完全聚合，可全局设置 |
| range_seconds | 是 | 选取时间范围, 开始时间=now-range_seconds, 结束时间=now，可全局设置 | 

## 感谢

* [aliyun-exporter](https://github.com/aylei/aliyun-exporter)
* [cloudwatch-exporter](https://github.com/prometheus/cloudwatch_exporter)
* [tencent-exporter](https://github.com/tencentyun/tencentcloud-exporter)
