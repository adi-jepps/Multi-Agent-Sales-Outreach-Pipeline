"""
Structured output schemas used by the research crew.

Keeping this separate means the task config (tasks.yaml) and any downstream
consumer (e.g. the email generator, in a future module) can import the same
shape without caring how the research was produced.
"""

from pydantic import BaseModel, Field


class CompanyResearch(BaseModel):
    values_alignment: str = Field(
        description=(
            "1-2 sentences on whether the company has stated sustainability/ESG "
            "commitments aligned with a carbon-reduction, circular-economy pitch. "
            "'none found' if nothing concrete turned up."
        )
    )
    recent_relevant_news: str = Field(
        description=(
            "1-2 sentences on recent (last 6-12 months) news, press releases, or "
            "posts relevant to sustainability, facility changes, or ESG reporting. "
            "'none found' if nothing relevant turned up."
        )
    )
    facility_notes: str = Field(
        description=(
            "Any mention of office size, facility type, or estate/property details "
            "found during research. 'none found' if nothing turned up."
        )
    )


class EmailDraft(BaseModel):
    subject: str = Field(description="Email subject line, under 60 characters.")
    body: str = Field(
        description=(
            "Email body, plain text, under 150 words. Personalized using the "
            "campaign agenda and the contact/company research findings, opening "
            "with a specific researched detail rather than generic flattery, and "
            "ending in exactly one clear call to action."
        )
    )
