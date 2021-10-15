import logging
from datetime import timedelta
from typing import Dict, List, Optional, Set
from marshmallow import Schema, fields, post_load, validate
from dataclasses import dataclass, field

@dataclass
class ResourceTypeSelection:
    service: str
    resource_type: str


@dataclass
class TagSelectRule:
    resource_id_dimension: str
    resource_type_selection: ResourceTypeSelection
    regions: List[str]


@dataclass
class MetricRule:
    namespace: str
    metric_name: str
    dimensions: List[Dict[str, str]] = field(default_factory=list)
    group_by: List[str] = field(default_factory=list)
    statistics: List[str] = field(default_factory=lambda: ['Maximum', 'Minimum', 'Average', 'Value', 'Sum'])
    period_seconds: Optional[int] = field(default=None)
    set_timestamp: Optional[bool] =  field(default=True)
    delay_seconds: Optional[timedelta] = field(default=None)
    range_seconds: Optional[timedelta] = field(default=None)
    tag_select: Optional[TagSelectRule] = field(default=None)


@dataclass
class Endpoint:
    metrics: str = field(default="metrics.aliyuncs.com")


@dataclass
class Config:
    metrics: List[MetricRule]
    endpoint: Endpoint
    log_level: str = field(default="WARNING")
    period_seconds: int = field(default=60)
    set_timestamp: bool =  field(default=True)
    delay_seconds: timedelta = field(default=timedelta(seconds=60))
    range_seconds: timedelta = field(default=timedelta(seconds=300))


class _BaseSchema(Schema):
    delay_seconds = fields.TimeDelta("seconds")
    range_seconds = fields.TimeDelta("seconds")
    period_seconds = fields.Integer()
    set_timestamp = fields.Boolean()


class ResourceTypeSelectionSchema(Schema):
    service = fields.String(required=True)
    resource_type = fields.String(required=True)

    @post_load
    def create(self, data, **kwargs):
        return ResourceTypeSelection(**data)


class TagSelectRuleSchema(Schema):
    resource_id_dimension = fields.String(required=True)
    resource_type_selection = fields.Nested(ResourceTypeSelectionSchema, required=True)
    regions = fields.List(fields.String, required=True)

    @post_load
    def create(self, data, **kwargs):
        return TagSelectRule(**data)


class MetricRuleSchema(_BaseSchema):
    namespace = fields.String(required=True)
    metric_name = fields.String(required=True)
    dimensions = fields.List(fields.Dict(keys=fields.String(), values=fields.String()))
    group_by = fields.List(fields.String())
    statistics = fields.List(fields.String())
    tag_select = fields.Nested(TagSelectRuleSchema)

    @post_load
    def create(self, data, **kwargs):
        return MetricRule(**data)


class EndpointSchema(Schema):
    metrics = fields.String()

    @post_load
    def create(self, data, **kwargs):
        return Endpoint(**data)

class ConfigSchema(_BaseSchema):
    metrics = fields.List(fields.Nested(MetricRuleSchema), required=True)
    log_level = fields.String(validate=validate.OneOf(logging._nameToLevel))
    endpoint = fields.Nested(EndpointSchema)

    @post_load
    def create(self, data, **kwargs):
        return Config(**data)
