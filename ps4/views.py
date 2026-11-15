"""
Public user-research pages for FSAD Problem Set 3 (served at /ps4/).

Plain Django views + templates, no login, no database: all content lives in
content.py and is synthetic or anonymised (personas are fictional composites;
participants appear only as codes such as P1).
"""
from django.http import Http404
from django.shortcuts import render

from . import content as c


def _ctx(**extra):
    return {"project": c.PROJECT, "participants": c.PARTICIPANTS,
            "personas": c.PERSONAS, "scenarios": c.SCENARIOS, **extra}


def index(request):
    return render(request, "ps4/index.html", _ctx())


def persona(request, slug):
    p = c.PERSONAS_BY_SLUG.get(slug)
    if p is None:
        raise Http404("No such persona.")
    findings = [f for f in c.FINDINGS if f["id"] in p["findings"]]
    scenario = c.SCENARIOS_BY_SLUG[p["scenario"]]
    return render(request, "ps4/persona.html", _ctx(persona=p, persona_findings=findings,
                                                    scenario=scenario))


def scenario(request, slug):
    s = c.SCENARIOS_BY_SLUG.get(slug)
    if s is None:
        raise Http404("No such scenario.")
    owner = c.PERSONAS_BY_SLUG.get(s.get("persona"))
    return render(request, "ps4/scenario.html", _ctx(scenario=s, owner=owner))


def findings(request):
    return render(request, "ps4/findings.html",
                  _ctx(findings=c.FINDINGS, disagreements=c.DISAGREEMENTS,
                       open_questions=c.OPEN_QUESTIONS))


def requirements(request):
    return render(request, "ps4/requirements.html",
                  _ctx(roles=c.ROLES, matrix=c.MATRIX, stories=c.USER_STORIES,
                       data_rows=c.DATA_ROWS, privacy_notes=c.PRIVACY_NOTES))


def mvp(request):
    return render(request, "ps4/mvp.html",
                  _ctx(decisions=c.DECISIONS, mvp_features=c.MVP_FEATURES,
                       out_of_scope=c.OUT_OF_SCOPE, changes=c.CHANGES_FROM_PROPOSAL))


def prototype(request):
    """Clickable prototype used in the Q3 feedback sessions (screens of the real app, no login)."""
    return render(request, "ps4/prototype.html", {"project": c.PROJECT})
