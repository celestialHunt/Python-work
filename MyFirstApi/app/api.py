from app.resources import contact_bp, todo_bp

BLUEPRINTS = [
    contact_bp,
    todo_bp
]


def register_blueprints(api):
    """
    Dynamically registers all blueprints defined in the BLUEPRINTS list.
    """
    for blp in BLUEPRINTS:
        api.register_blueprint(blp)
