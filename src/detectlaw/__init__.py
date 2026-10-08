"""detect-law: explainable AI-text triage with a bounded false-positive rate.

    from detectlaw import Engine
    print(Engine().detect(open("essay.txt").read())["verdict"])   # ai | no_evidence | undecided
"""
__version__ = "0.3.0"


def __getattr__(name):                     # load the models only when the engine is used
    if name == "Engine":
        from .engine import Engine
        return Engine
    raise AttributeError(name)
