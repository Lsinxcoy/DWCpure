from dwc.harness.reflection_library import (
    EditEvidence,
    ExperienceEntry,
    ReflectionLibrary,
    attribute_edit,
    write_experience,
)


def _entry(**extra):
    values = dict(
        cue="Repeated domain read",
        applicable_scope="domain",
        component="tool guidance",
        operation="remove_redundant_read",
        supporting_contrasts=("contrast:1", "contrast:2"),
        edit_evidence_refs=("edit:1",),
        confidence="observed",
        confounded=False,
        source_harness_ref="harness:component-ref",
        evaluation_version="probe-v1",
        fact_scope="domain",
        revalidation_required=True,
    )
    values.update(extra)
    return ExperienceEntry(**values)


def test_adopted_does_not_imply_helped_and_single_probe_is_confounded():
    evidence = attribute_edit(
        edit_id="edit:1", candidate_refs=("candidate:1",),
        compose_decision="adopted", contrast_refs=("probe:1",),
        proposed_verdict="helped", adopted=True, components=("tool guidance",),
    )
    assert evidence.adopted
    assert evidence.verdict == "confounded"
    assert evidence.attribution_status == "unallocated"


def test_multicomponent_edit_is_confounded_without_isolation():
    evidence = attribute_edit(
        "edit:1", ("candidate:1",), "adopted", ("p1", "p2"),
        proposed_verdict="helped", adopted=False,
        components=("memory", "tool guidance"), isolated=False,
    )
    assert evidence.verdict == "confounded"
    assert not evidence.adopted


def test_no_entry_is_not_retrievable_and_valid_entry_is_namespaced(tmp_path):
    library = ReflectionLibrary(tmp_path, namespace={
        "domain": "code", "protocol": "p1", "search_mode": "sequential", "evaluator_epoch": "e1",
    })
    rejected = write_experience(library, _entry(cue=""), sequence=1)
    assert rejected.status == "NO_ENTRY"
    assert library.retrieve("domain read", sequence=2) == ()
    accepted = write_experience(library, _entry(), sequence=1)
    assert accepted.status == "written"
    assert library.retrieve("domain read", sequence=2) == (_entry(),)
    assert library.retrieve("domain read", sequence=1) == ()


def test_workspace_fact_and_complete_harness_are_not_written(tmp_path):
    library = ReflectionLibrary(tmp_path, namespace={
        "domain": "code", "protocol": "p1", "search_mode": "parallel", "evaluator_epoch": "e1",
    })
    workspace = write_experience(library, _entry(fact_scope="workspace"), sequence=0)
    assert workspace.status == "NO_ENTRY"
    harness = write_experience(library, _entry(component="complete harness"), sequence=1)
    assert harness.status == "NO_ENTRY"


def test_namespace_isolation_and_prefix_resume_are_deterministic(tmp_path):
    namespace = {"domain": "code", "protocol": "p1", "search_mode": "s", "evaluator_epoch": "e"}
    library = ReflectionLibrary(tmp_path, namespace=namespace)
    write_experience(library, _entry(cue="first"), sequence=0)
    write_experience(library, _entry(cue="second"), sequence=1)
    assert library.retrieve("", sequence=2) == ()
    assert [entry.cue for entry in library.retrieve("", sequence=2)] == []
    assert [entry.cue for entry in library.retrieve("first second", sequence=2)] == []
    assert [entry.cue for entry in library.retrieve("first", sequence=2)] == ["first"]
    assert [entry.cue for entry in library.retrieve("second", sequence=2)] == ["second"]
    other = ReflectionLibrary(tmp_path, namespace={**namespace, "search_mode": "other"})
    assert other.retrieve("domain read", sequence=2) == ()
