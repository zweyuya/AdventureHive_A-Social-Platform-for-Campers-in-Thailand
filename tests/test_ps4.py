"""Problem Set 3: the public /ps4/ research pages."""
import re

import pytest
from django.test import Client

from ps4 import content

PAGES = ["/ps4/", "/ps4/findings/", "/ps4/requirements/", "/ps4/mvp/", "/ps4/prototype/"] \
    + [f"/ps4/personas/{p['slug']}/" for p in content.PERSONAS] \
    + [f"/ps4/scenarios/{s['slug']}/" for s in content.SCENARIOS]


def _links(html):
    return set(re.findall(r'href="(/ps4/[^"#]*)', html))


@pytest.mark.django_db
@pytest.mark.parametrize("url", PAGES)
def test_every_page_is_public_and_links_back_to_index(url):
    res = Client().get(url)  # anonymous visitor
    assert res.status_code == 200
    html = res.content.decode()
    assert 'href="/ps4/"' in html
    assert "TO FILL" not in html and "{{" not in html


@pytest.mark.django_db
def test_index_links_to_every_persona_scenario_and_result_page():
    links = _links(Client().get("/ps4/").content.decode())
    for url in PAGES:
        assert url in links, url


@pytest.mark.django_db
def test_has_two_or_three_distinct_personas_each_linking_to_its_scenario():
    assert 2 <= len(content.PERSONAS) <= 3
    names = set()
    for p in content.PERSONAS:
        html = Client().get(f"/ps4/personas/{p['slug']}/").content.decode()
        assert f"/ps4/scenarios/{p['scenario']}/" in _links(html)
        names.add(p["name"])
        assert p["name"] in html
    assert len(names) == len(content.PERSONAS)


@pytest.mark.django_db
def test_primary_user_has_a_mobile_scenario():
    primary = next(p for p in content.PERSONAS if p["primary"])
    assert content.SCENARIOS_BY_SLUG[primary["scenario"]]["mobile"]


@pytest.mark.django_db
def test_every_link_on_every_page_works():
    client = Client()
    seen = set()
    for url in PAGES:
        for link in _links(client.get(url).content.decode()):
            if link not in seen:
                seen.add(link)
                assert client.get(link).status_code == 200, link


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/ps4/personas/nobody/", "/ps4/scenarios/nothing/"])
def test_unknown_persona_or_scenario_is_404(url):
    assert Client().get(url).status_code == 404


def test_matrix_rows_cover_every_role():
    for action, cells in content.MATRIX:
        assert len(cells) == len(content.ROLES), action


def test_participants_are_codes_only():
    for p in content.PARTICIPANTS:
        assert re.fullmatch(r"P\d+", p["code"])
        assert set(p) <= {"code", "user_class", "mode", "duration"}


@pytest.mark.django_db
def test_prototype_screens_and_hotspots_exist():
    import json
    from pathlib import Path
    from django.conf import settings
    html = Client().get("/ps4/prototype/").content.decode()
    data = json.loads(re.search(r"const SCREENS = (\{.*?\});\n", html).group(1))
    folder = Path(settings.BASE_DIR) / "ps4" / "static" / "ps4" / "prototype"
    for sid, screen in data.items():
        assert (folder / f"{sid}.jpg").exists(), sid
        for h in screen["hotspots"]:
            assert h["to"] == "done" or h["to"] in data, (sid, h)
