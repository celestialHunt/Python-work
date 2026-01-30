from marshmallow import Schema, fields, validate


class ContactSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=30))
    email = fields.Email(required=True, validate=validate.Email())
    phone = fields.Str(required=True, validate=validate.Length(min=10, max=13))
    address = fields.Str(required=False)
    city = fields.Str(required=False)
    state = fields.Str(required=False)
    zip = fields.Str(required=False)
    country = fields.Str(required=False)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
