from marshmallow import Schema, fields, validate


class TodoSchema(Schema):
    id = fields.Int(dump_only=True)
    title = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    task = fields.Str(required=True)
    done = fields.Bool(load_default=False)
    created_at = fields.DateTime(dump_only=True)
