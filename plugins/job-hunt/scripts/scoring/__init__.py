"""Deterministic fit scoring between the workspace master CV and a job description.

Pure, offline, workspace-read-only. Reuses tailor.ats for ALL keyword work — this
package never re-implements keyword extraction or matching. A fit score is a
diagnostic only: a low score routes the user to focus elsewhere or /job-upskill,
and is NEVER a reason to fabricate skills or experience the master does not contain.
"""
