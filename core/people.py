"""How a user appears next to their content everywhere in the API."""


def avatar_url(user) -> str | None:
    profile = getattr(user, "profile", None)
    return profile.avatar.url if profile and profile.avatar else None


def display_name(user) -> str:
    profile = getattr(user, "profile", None)
    return profile.display_name if profile else "Unknown"


def person(user) -> dict:
    return {"id": user.pk, "display_name": display_name(user), "avatar": avatar_url(user)}
