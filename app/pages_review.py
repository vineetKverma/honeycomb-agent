"""Daily Review page: spaced-repetition picks, then quiz + grade + record.

Gemini is called ONLY on "Quiz me on this" (generate) and "Submit Answer"
(grade) -- never on page load.
"""
import streamlit as st
from bson import ObjectId

import mastery
import quiz

_LEVEL_COLOR = {"weak": "red", "developing": "orange", "solid": "green", "untested": "gray"}


def _badge(level: str) -> str:
    return f":{_LEVEL_COLOR.get(level, 'gray')}[{level.upper()}]"


def _stars(score: int) -> str:
    return "*" * score + "-" * (5 - score)


def render_review_page() -> None:
    st.header("Daily review")

    if st.button("Get today's review picks", type="primary"):
        st.session_state["review_candidates"] = mastery.get_review_candidates(limit=5)

    candidates = st.session_state.get("review_candidates")
    if candidates is None:
        st.info("Click the button to get your spaced-repetition picks.")
        return
    if not candidates:
        st.success("Nothing is due for review right now. Nice work!")
        return

    for c in candidates:
        _render_candidate(c)


def _render_candidate(c: dict) -> None:
    name = c["name"]
    info = c["mastery_info"]
    definition = c.get("definition", "")
    with st.container(border=True):
        st.markdown(f"### {name} &nbsp; {_badge(info['mastery_level'])}")
        st.caption(definition[:150] + ("..." if len(definition) > 150 else ""))
        days = info["days_since_last_review"]
        st.caption(f"Days since last review: {days if days is not None else 'never'}")

        if st.button("Quiz me on this", key=f"quizbtn_{name}"):
            with st.spinner("Generating a question..."):
                st.session_state[f"quiz_{name}"] = quiz.generate_quiz(
                    {"name": name, "definition": definition}
                )
            st.session_state.pop(f"grade_{name}", None)

        q = st.session_state.get(f"quiz_{name}")
        if q:
            _render_quiz(name, info, q)


def _render_quiz(name: str, info: dict, q: dict) -> None:
    st.markdown(f"**Question:** {q['question']}")
    with st.expander("spoiler: expected answer outline"):
        for pt in q["expected_answer_outline"]:
            st.write(f"- {pt}")

    answer = st.text_area("Your answer", key=f"answer_{name}")
    if st.button("Submit Answer", key=f"submitbtn_{name}"):
        with st.spinner("Grading..."):
            grade = quiz.grade_answer(q["question"], q["expected_answer_outline"], answer)
            cid = ObjectId(info["concept_id"])
            mastery.record_event(cid, name, grade["score"], answer, grade["missed_points"])
            grade["new_level"] = mastery.compute_mastery(cid)["mastery_level"]
        st.session_state[f"grade_{name}"] = grade

    grade = st.session_state.get(f"grade_{name}")
    if grade:
        st.markdown(f"**Score:** {grade['score']}/5 &nbsp; `{_stars(grade['score'])}`")
        st.markdown(f"**Feedback:** {grade['feedback']}")
        if grade["missed_points"]:
            st.markdown("**Missed points:**")
            for mp in grade["missed_points"]:
                st.write(f"- {mp}")
        st.info(f"New mastery level: {grade['new_level']}")
