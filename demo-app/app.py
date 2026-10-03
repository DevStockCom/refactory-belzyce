"""TableStory: a recipe discovery app for mobile and TV."""

from __future__ import annotations

from flask import Flask, abort, jsonify, render_template, request

from domain import (
    CookbookStore,
    build_rails,
    search_recipes,
    search_text,
    validate_rails,
)
from recipes import load_recipes, total_minutes

TV_UA_HINTS = (
    "smart-tv",
    "smarttv",
    "tizen",
    "web0s",
    "webos",
    "appletv",
    "googletv",
    "android tv",
    "roku",
    "viera",
    "hbbtv",
    "crkey",
    "aftb",
    "bravia",
)


def is_tv_request(args, user_agent) -> bool:
    """TV mode: ?mode=tv or a TV user-agent hint; any other explicit mode opts out."""
    mode = args.get("mode")
    if mode:
        return mode.lower() == "tv"
    agent = (user_agent or "").lower()
    return any(hint in agent for hint in TV_UA_HINTS)


def register_template_helpers(app: Flask) -> None:
    app.jinja_env.filters["total_minutes"] = total_minutes
    app.jinja_env.filters["search_text"] = search_text


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=testing)
    recipes = load_recipes()
    validate_rails(build_rails(recipes, []), recipes)
    by_id = {recipe["id"]: recipe for recipe in recipes}
    store = CookbookStore(recipes)
    app.extensions["cookbook"] = store
    register_template_helpers(app)

    def is_tv() -> bool:
        return is_tv_request(request.args, request.headers.get("User-Agent"))

    @app.get("/")
    def index():
        tv = is_tv()
        context = {
            "recipes": recipes,
            "saved_ids": set(store.ids()),
            "tv": tv,
            "mode": "tv" if tv else "mobile",
        }
        if tv:
            return render_template("tv_home.html", rails=build_rails(recipes, store.ids()), **context)
        return render_template("index.html", **context)

    @app.get("/recipe/<recipe_id>")
    def detail(recipe_id: str):
        recipe = by_id.get(recipe_id)
        if not recipe:
            abort(404)
        tv = is_tv()
        return render_template(
            "tv_detail.html" if tv else "detail.html",
            recipe=recipe,
            saved=store.contains(recipe_id),
            tv=tv,
            mode="tv" if tv else "mobile",
            back_url="/?mode=tv" if tv else "/",
        )

    @app.get("/api/recipes")
    def api_recipes():
        return jsonify(search_recipes(recipes, request.args.get("q", "")))

    @app.get("/api/recipes/<recipe_id>")
    def api_recipe(recipe_id: str):
        recipe = by_id.get(recipe_id)
        return jsonify(recipe) if recipe else (jsonify({"error": "Recipe not found"}), 404)

    @app.get("/api/cookbook")
    def api_cookbook():
        return jsonify(store.recipes())

    @app.post("/api/cookbook")
    def api_cookbook_add():
        body = request.get_json(silent=True)
        recipe_id = body.get("id") if isinstance(body, dict) else None
        if not store.add(recipe_id):
            return jsonify({"error": "Unknown recipe"}), 400
        return jsonify({"recipe_ids": store.ids()}), 201

    @app.delete("/api/cookbook/<recipe_id>")
    def api_cookbook_remove(recipe_id: str):
        store.remove(recipe_id)
        return jsonify({"recipe_ids": store.ids()})

    @app.get("/api/rails")
    def api_rails():
        return jsonify(build_rails(recipes, store.ids()))

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("404.html"), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
