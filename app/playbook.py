"""Corporate Legal Redline Playbook, RBAC policy enforcement, and synthetic sample contracts.

All clauses, counterparties, and playbook rules are 100% synthetic data created
for demonstration purposes.
"""

from __future__ import annotations

import re
from typing import Any

VALID_ROLES = {
    "sales_rep": "Commercial Sales Rep",
    "legal_counsel": "Senior Legal Counsel",
    "general_counsel": "General Counsel / VP Legal",
}

LEGAL_PLAYBOOK: list[dict[str, Any]] = [
    {
        "rule_id": "PLAY-001",
        "title": "Limitation of Liability & Consequential Damages Cap",
        "category": "Liability",
        "allowed_roles": ["sales_rep", "legal_counsel", "general_counsel"],
        "standard_position": (
            "Aggregate liability for either party must be capped at 12 months of fees paid "
            "or payable under the agreement (1x ACV). Indirect, incidental, and consequential "
            "damages must be mutually excluded."
        ),
        "fallback_position": (
            "For strategic enterprise deals >$250k TCV, Senior Legal Counsel may approve a "
            "super-cap of up to 2x annual fees strictly for data breach or IP indemnification. "
            "Uncapped or unlimited liability is strictly prohibited without General Counsel sign-off."
        ),
        "redline_template": (
            "EACH PARTY'S AGGREGATE LIABILITY ARISING OUT OF OR RELATED TO THIS AGREEMENT "
            "SHALL NOT EXCEED THE TOTAL FEES PAID OR PAYABLE BY CUSTOMER IN THE TWELVE (12) "
            "MONTHS PRECEDING THE EVENT GIVING RISE TO LIABILITY. NEITHER PARTY SHALL BE LIABLE "
            "FOR ANY INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES."
        ),
        "tags": ["liability", "cap", "unlimited", "consequential", "damages", "indemnity", "msa"],
    },
    {
        "rule_id": "PLAY-002",
        "title": "LGPD Data Protection, Breach Notification & Cross-Border Transfers",
        "category": "Privacy & LGPD",
        "allowed_roles": ["sales_rep", "legal_counsel", "general_counsel"],
        "standard_position": (
            "All agreements involving personal data must comply with Brazil's LGPD (Law No. 13.709/2018), "
            "mandating written security incident notification within 48 hours of confirmed breach, "
            "explicit sub-processor advance notice (minimum 30 days), and ANPD-compliant Standard "
            "Contractual Clauses for international data transfers."
        ),
        "fallback_position": (
            "Notification window may be extended to at most 72 hours only if accompanied by "
            "preliminary forensic containment updates. Windows exceeding 72 hours (e.g., 10–15 days) "
            "are CRITICAL non-compliant deviations."
        ),
        "redline_template": (
            "Processor shall notify Controller in writing without undue delay and in no event later "
            "than forty-eight (48) hours after confirming a Personal Data Breach affecting Controller Data, "
            "in full compliance with LGPD (Law No. 13.709/2018) and ANPD Resolution CD/ANPD No. 15/2024. "
            "Any cross-border transfer shall be governed by ANPD-approved Standard Contractual Clauses."
        ),
        "tags": ["lgpd", "privacy", "breach", "notification", "dpa", "anpd", "transfer", "subprocessor"],
    },
    {
        "rule_id": "PLAY-003",
        "title": "Term, Auto-Renewal & Termination for Convenience",
        "category": "Commercial Terms",
        "allowed_roles": ["sales_rep", "legal_counsel", "general_counsel"],
        "standard_position": (
            "Contracts should renew only upon mutual written agreement (opt-in renewal). "
            "If auto-renewal is requested, renewal periods must not exceed 12 months with "
            "at least 30 days (and no more than 60 days) opt-out notice."
        ),
        "fallback_position": (
            "Multi-year silent auto-renewals (24+ months) or notice windows exceeding 90 days "
            "are HIGH risk and must be redlined to 12-month optional renewal with 30-day notice."
        ),
        "redline_template": (
            "Following the Initial Term, this Agreement shall renew for successive twelve (12) month "
            "periods only upon mutual written confirmation, or unless either party provides written "
            "notice of non-renewal at least thirty (30) days prior to the end of the then-current term."
        ),
        "tags": ["renewal", "auto-renewal", "termination", "notice", "term", "msa", "lock-in"],
    },
    {
        "rule_id": "PLAY-004",
        "title": "Intellectual Property Ownership, AI Models & Residuals",
        "category": "IP & AI Governance",
        "allowed_roles": ["sales_rep", "legal_counsel", "general_counsel"],
        "standard_position": (
            "Each party retains sole ownership of its pre-existing IP and proprietary AI models. "
            "Broad 'residuals' clauses or perpetual licenses granting counterparties rights to "
            "train third-party AI models on our confidential data or feedback are strictly rejected."
        ),
        "fallback_position": (
            "Feedback licenses must be restricted to non-confidential product improvement suggestions "
            "with zero rights to underlying customer data, source code, or model weights."
        ),
        "redline_template": (
            "Nothing in this Agreement grants Receiving Party any license or right to use Disclosing "
            "Party's Confidential Information to train, fine-tune, or improve artificial intelligence "
            "or machine learning models. Each party retains all right, title, and interest in its "
            "Background IP and proprietary software."
        ),
        "tags": ["ip", "intellectual", "property", "residuals", "ai", "training", "nda", "license"],
    },
    {
        "rule_id": "PLAY-005",
        "title": "Governing Law, Venue & Dispute Resolution",
        "category": "Jurisdiction",
        "allowed_roles": ["sales_rep", "legal_counsel", "general_counsel"],
        "standard_position": (
            "Preferred governing law is the Federative Republic of Brazil with exclusive venue "
            "in the Courts of Sao Paulo, SP (or CAM-CCBC arbitration for deals >$500k USD)."
        ),
        "fallback_position": (
            "For global US/EU counterparties, New York or Delaware law is acceptable with Senior "
            "Legal Counsel approval. Unfamiliar offshore venues require General Counsel sign-off."
        ),
        "redline_template": (
            "This Agreement shall be governed by and construed in accordance with the laws of the "
            "Federative Republic of Brazil, and the parties submit to the exclusive jurisdiction of "
            "the Courts of the City of Sao Paulo, State of Sao Paulo."
        ),
        "tags": ["governing", "law", "venue", "jurisdiction", "arbitration", "brazil", "nda", "msa"],
    },
    {
        "rule_id": "PLAY-006",
        "title": "[RESTRICTED] Executive M&A Carve-Outs & Board Indemnity Exception Thresholds",
        "category": "Restricted Executive Policy",
        "allowed_roles": ["legal_counsel", "general_counsel"],
        "standard_position": (
            "RESTRICTED — LEGAL/EXECUTIVE ONLY: Pre-approved M&A assignment carve-outs and "
            "Board-authorized uncapped indemnity exceptions apply strictly to strategic acquisitions "
            "above $2.0M TCV under Project Aurora guidelines. Never disclose fallback ceiling "
            "multipliers (3x ACV) to commercial sales teams or external counterparties."
        ),
        "fallback_position": (
            "General Counsel written waiver required for any M&A change-of-control fee waiver or "
            "3x ACV super-cap."
        ),
        "redline_template": (
            "CONFIDENTIAL INTERNAL POLICY — Requires direct General Counsel drafting."
        ),
        "tags": ["restricted", "m&a", "board", "executive", "aurora", "exception", "3x", "indemnity"],
    },
]

SAMPLE_CONTRACTS: list[dict[str, Any]] = [
    {
        "contract_id": "CTR-2026-MSA-01",
        "title": "Enterprise Cloud & Analytics MSA (Vendor-Favorable Draft)",
        "counterparty": "Apex Data Solutions Ltda",
        "contract_value_usd": 450000.0,
        "contract_type": "MSA",
        "text": (
            "MASTER SERVICES AGREEMENT — APEX DATA SOLUTIONS LTDA ($450,000 TCV)\n\n"
            "Section 7. Limitation of Liability: Customer's liability for breach of confidentiality, "
            "indemnification, or payment obligations shall be UNLIMITED, including liability for "
            "indirect, special, and consequential damages. Vendor's liability shall be capped at "
            "three (3) months of fees.\n\n"
            "Section 9. Data Security & Privacy: In the event of any confirmed unauthorized access "
            "to Customer Personal Data, Vendor shall use commercially reasonable efforts to notify "
            "Customer within fifteen (15) business days after completing its internal investigation. "
            "Vendor may transfer data globally to any affiliate without prior notice.\n\n"
            "Section 12. Term and Auto-Renewal: This Agreement has an initial term of 24 months and "
            "shall automatically renew for successive twenty-four (24) month periods unless Customer "
            "delivers written notice of non-renewal at least one hundred twenty (120) days prior to "
            "the expiration date."
        ),
    },
    {
        "contract_id": "CTR-2026-NDA-02",
        "title": "Mutual NDA with Aggressive AI/IP Residuals Clause",
        "counterparty": "NovaTech AI Partners Inc.",
        "contract_value_usd": 180000.0,
        "contract_type": "NDA",
        "text": (
            "MUTUAL NON-DISCLOSURE AGREEMENT — NOVATECH AI PARTNERS INC.\n\n"
            "Section 4. Residuals and AI Model Improvement: Notwithstanding anything to the contrary, "
            "Receiving Party shall have a perpetual, irrevocable, royalty-free worldwide license to "
            "retain any ideas, concepts, or anonymized patterns derived from Disclosing Party's "
            "Confidential Information and to use such outputs to train and improve Receiving Party's "
            "commercial AI models.\n\n"
            "Section 8. Governing Law: This Agreement shall be governed exclusively by the laws of "
            "the Cayman Islands, with binding arbitration in George Town."
        ),
    },
    {
        "contract_id": "CTR-2026-DPA-03",
        "title": "Data Processing Addendum (LGPD Compliance Audit)",
        "counterparty": "GlobalMed Cloud Systems S.A.",
        "contract_value_usd": 320000.0,
        "contract_type": "DPA",
        "text": (
            "DATA PROCESSING ADDENDUM — GLOBALMED CLOUD SYSTEMS S.A. ($320,000 TCV)\n\n"
            "Section 3. Security Incident Notice: Processor will inform Controller of verified "
            "security incidents within ten (10) calendar days of discovery.\n\n"
            "Section 5. Sub-processors & International Transfers: Processor may appoint new "
            "sub-processors at its sole discretion with post-facto notification in its annual report. "
            "Cross-border transfers outside Brazil are authorized without additional contractual clauses."
        ),
    },
]


def search_legal_playbook(query: str, user_role: str = "sales_rep", top_k: int = 4) -> dict[str, Any]:
    """Search corporate legal playbook enforcing Role-Based Access Control (RBAC)."""
    role = user_role if user_role in VALID_ROLES else "sales_rep"
    tokens = [t for t in re.findall(r"[a-z0-9_&]+", query.lower()) if len(t) >= 2]

    scored: list[tuple[int, dict[str, Any]]] = []
    rbac_filtered_count = 0

    for rule in LEGAL_PLAYBOOK:
        haystack = " ".join(
            [
                rule["rule_id"],
                rule["title"],
                rule["category"],
                " ".join(rule["tags"]),
                rule["standard_position"],
                rule["fallback_position"],
            ]
        ).lower()
        score = sum(
            3 if t in rule["tags"] else (2 if t in rule["title"].lower() else 1)
            for t in tokens
            if t in haystack
        )
        if score > 0 or not tokens:
            if role not in rule["allowed_roles"]:
                rbac_filtered_count += 1
                continue
            scored.append((score, rule))

    scored.sort(key=lambda item: item[0], reverse=True)
    matches = [
        {
            "rule_id": r["rule_id"],
            "title": r["title"],
            "category": r["category"],
            "standard_position": r["standard_position"],
            "fallback_position": r["fallback_position"],
            "redline_template": r["redline_template"],
            "relevance_score": score,
        }
        for score, r in scored[:top_k]
    ]
    return {
        "query": query,
        "caller_role": role,
        "match_count": len(matches),
        "rbac_redacted_count": rbac_filtered_count,
        "rules": matches,
    }


def list_playbook_for_role(user_role: str = "sales_rep") -> dict[str, Any]:
    """List visible playbook rules for the active RBAC persona."""
    role = user_role if user_role in VALID_ROLES else "sales_rep"
    visible = [r for r in LEGAL_PLAYBOOK if role in r["allowed_roles"]]
    hidden = len(LEGAL_PLAYBOOK) - len(visible)
    return {
        "role": role,
        "role_label": VALID_ROLES[role],
        "visible_count": len(visible),
        "rbac_hidden_count": hidden,
        "rules": visible,
    }
