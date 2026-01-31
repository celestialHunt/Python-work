from flask.views import MethodView
from flask_smorest import Blueprint, abort
from app.models import TodoModel
from app.schemas import TodoSchema
from app.database import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError


bp = Blueprint(
    "Todos",
    __name__,
    description="Operations on todos"
)


@bp.route("/todo")
class TodoList(MethodView):
    @bp.response(200, TodoSchema(many=True))
    def get(self):
        return TodoModel.query.all()

    @bp.arguments(TodoSchema)
    @bp.response(201, TodoSchema)
    def post(self, new_todo):
        todo = TodoModel(**new_todo)
        try:
            db.session.add(todo)
            db.session.commit()
        except IntegrityError:
            abort(
                400,
                message="A todo with same title or skill already exists."
            )
        except SQLAlchemyError:
            abort(
                500,
                message="An error occurred while creating the contact."
            )

        return todo


@bp.route("/todo/<int:todo_id>")
class TodoResource(MethodView):
    @bp.response(200, TodoSchema)
    def get(self, todo_id):
        return TodoModel.query.get_or_404(todo_id)

    def put(self, data_toUpdate, todo_id):
        todo = TodoModel.query.get_or_404(todo_id)
        for key, value in data_toUpdate.items():
            setattr(todo, key, value)

        db.session.commit()

        return todo

    @bp.response(204)
    def delete(self, todo_id):
        todo = TodoModel.query.get_or_404(todo_id)

        db.session.delete(todo)
        db.session.commit()

        return None
