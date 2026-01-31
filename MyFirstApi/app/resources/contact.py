from flask.views import MethodView
from flask_smorest import Blueprint, abort
from app.models import ContactModel
from app.schemas import ContactSchema
from app.database import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

bp = Blueprint(
    "Contacts",
    __name__,
    description="Operations on contacts"
)


@bp.route("/contact")
class ContactList(MethodView):
    @bp.response(200, ContactSchema(many=True))
    def get(self):
        return ContactModel.query.all()

    @bp.arguments(ContactSchema)
    @bp.response(201, ContactSchema)
    def post(self, new_contact):
        contact = ContactModel(**new_contact)
        try:
            db.session.add(contact)
            db.session.commit()
        except IntegrityError:
            abort(
                400,
                message="A contact with that email or phone already exists."
            )
        except SQLAlchemyError:
            abort(
                500,
                message="An error occurred while creating the contact."
            )
        return contact


@bp.route("/contact/<int:contact_id>")
class ContactResource(MethodView):
    @bp.response(200, ContactSchema)
    def get(self, contact_id):
        return ContactModel.query.get_or_404(contact_id)

    @bp.arguments(ContactSchema)
    @bp.response(200, ContactSchema)
    def put(self, update_contact, contact_id):
        contact = ContactModel.query.get_or_404(contact_id)
        for key, value in update_contact.items():
            setattr(contact, key, value)

        db.session.commit()

        return contact

    @bp.response(204)
    def delete(self, contact_id):
        contact = ContactModel.query.get_or_404(contact_id)

        db.session.delete(contact)
        db.session.commit()

        return None
