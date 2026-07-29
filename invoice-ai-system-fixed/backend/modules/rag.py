"""
RAG (Retrieval-Augmented Generation) Engine
Answers natural-language questions about invoices using Groq LLM + DB context.

Account/permission model:
- Regular users: can ask about invoices (their own only, as before) and can
  ask "user account" style questions, but only ever get back THEIR OWN
  account info — never any other user's.
- Admin: can ask about invoices (defaults to ALL users' invoices, or a
  specific named user's invoices if a user is named in the question), and
  can ask "user account" style questions — either the full user list, or
  a specific named user's account info if a name is mentioned.
- Named-user lookup works by matching a username or full name against the
  actual users in the database (safe: no free-text guessing of names that
  don't exist), so "tell me about bob" or "invoices uploaded by Bob Smith"
  both resolve correctly.
- Never includes password_hash / legacy_hashed_password / tokens anywhere.
"""
import logging
import re

from sqlalchemy.orm import Session
from sqlalchemy import desc

from config import settings

logger = logging.getLogger(__name__)

# Word-boundary match: catches "user", "users", "username", "user name",
# "account", "accounts" etc. anywhere in the question, in any phrasing.
_USER_ACCOUNT_PATTERN = re.compile(
    r"\b(user\s*names?|usernames?|users?|accounts?|admin\s*account|registered\s*(user|account)s?)\b",
    re.IGNORECASE,
)


class RAGEngine:
    def __init__(self):
        self.client = None
        self._init_groq()

    def _init_groq(self):
        try:
            if settings.groq_api_key:
                from groq import Groq
                self.client = Groq(api_key=settings.groq_api_key)
                logger.info("Groq client initialized for RAG.")
            else:
                logger.warning("GROQ_API_KEY not set; RAG will use DB-only answers.")
        except Exception as e:
            logger.warning("Groq init failed: %s", e)

    # ──────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────

    def query(
        self,
        question: str,
        db: Session,
        caller_id: str,
        caller_role: str | None = None,
    ) -> dict:
        """
        caller_id/caller_role are always the CURRENTLY LOGGED-IN user — used
        to enforce permissions. They are never taken from the question text.
        """
        is_admin = caller_role == "admin"
        named_user = self._find_named_user(question, db) if is_admin else None

        if self._is_user_account_question(question):
            return self._answer_account_question(
                question, db, caller_id=caller_id, is_admin=is_admin, named_user=named_user
            )

        return self._query_invoices(
            question, db, caller_id=caller_id, is_admin=is_admin, named_user=named_user
        )

    # ──────────────────────────────────────────────
    # Named-user resolution (admin only calls this)
    # ──────────────────────────────────────────────

    def _find_named_user(self, question: str, db: Session):
        """
        Looks for a real, existing username or full name mentioned inside
        the question. Only ever matches against actual DB users — never
        invents or guesses a name. Returns the single best (longest) match,
        or None if no user is clearly named.
        """
        from database.db import User

        users = db.query(User).all()
        q_lower = question.lower()

        candidates = []
        for u in users:
            for name in (u.username, u.full_name):
                if name and len(name.strip()) >= 3 and name.strip().lower() in q_lower:
                    candidates.append((len(name.strip()), u))

        if not candidates:
            return None

        # Prefer the longest matching name (most specific match).
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return candidates[0][1]

    # ──────────────────────────────────────────────
    # User-account questions
    # ──────────────────────────────────────────────

    def _is_user_account_question(self, question: str) -> bool:
        return bool(_USER_ACCOUNT_PATTERN.search(question))

    def _user_to_line(self, u) -> str:
        status = u.status or ("Active" if u.is_active else "Inactive")
        return (
            f"Username: {u.username} | Email: {u.email} | Full name: {u.full_name or '-'} | "
            f"Role: {u.role} | Status: {status} | Created: {u.created_at}"
        )

    def _user_to_source(self, u) -> dict:
        status = u.status or ("Active" if u.is_active else "Inactive")
        return {
            "type": "user_account",
            "user_id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "status": status,
        }

    def _answer_account_question(self, question, db, caller_id, is_admin, named_user):
        from database.db import User

        if not is_admin:
            # Regular users only ever see their own account, regardless of
            # any name they might type — no enumeration of other users.
            self_user = db.query(User).filter(User.id == caller_id).first()
            if not self_user:
                return {"answer": "Could not find your account.", "sources": []}
            context = self._user_to_line(self_user)
            sources = [self._user_to_source(self_user)]
            return self._render_user_answer(question, context, sources)

        # Admin path
        if named_user:
            context = self._user_to_line(named_user)
            sources = [self._user_to_source(named_user)]
            return self._render_user_answer(question, context, sources)

        # No specific name mentioned -> full user list
        users = db.query(User).order_by(desc(User.created_at)).all()
        if not users:
            return {"answer": "No user accounts found.", "sources": []}
        context = "\n".join(self._user_to_line(u) for u in users)
        sources = [self._user_to_source(u) for u in users][:10]
        return self._render_user_answer(question, context, sources)

    def _render_user_answer(self, question, context, sources):
        if self.client:
            try:
                answer = self._ask_groq_about_users(question, context)
                return {"answer": answer, "sources": sources}
            except Exception as e:
                logger.error("Groq user-account query failed: %s", e)
        return {"answer": self._db_fallback_user_answer(context), "sources": sources}

    # ──────────────────────────────────────────────
    # Invoice questions
    # ──────────────────────────────────────────────

    def _query_invoices(self, question: str, db: Session, caller_id: str, is_admin: bool, named_user=None) -> dict:
        from database.db import Invoice

        query = db.query(Invoice).filter(
            Invoice.extraction_status == "success",
            Invoice.deleted_at.is_(None),
        )

        if named_user:
                # Admin asked about a specific user's invoices -> full access
                # to that user's invoices, no restriction.
                query = query.filter(Invoice.owner_id == named_user.id)
            # else: no filter at all -> admin sees invoices across all users.
        else:
            # Regular users only ever see their own invoices.
            query = query.filter(Invoice.owner_id == caller_id)

        invoices = query.order_by(desc(Invoice.upload_time)).limit(20).all()

        if not invoices:
            return {
                "answer": "No processed invoices found yet. Upload and process some invoices first.",
                "sources": [],
            }

        filtered_invoices = self._filter_invoices(question, invoices)

        context_lines = []
        for inv in filtered_invoices:
            line = (
                f"Invoice #{inv.invoice_number} | Vendor: {inv.vendor_name} | "
                f"Amount: {inv.currency or 'INR'} {inv.total_amount} | "
                f"Date: {inv.invoice_date} | Status: {inv.validation_status} | "
                f"Duplicate: {'yes' if inv.is_duplicate else 'no'} | "
                f"Issues: {', '.join(inv.validation_errors or []) if inv.validation_errors else 'none'}"
            )
            context_lines.append(line)

        sources = self._build_sources(filtered_invoices)
        context = "\n".join(context_lines)

        if self.client:
            try:
                answer = self._ask_groq(question, context)
                return {"answer": answer, "sources": sources[:5]}
            except Exception as e:
                logger.error("Groq query failed: %s", e)

        answer = self._db_fallback_answer(question, filtered_invoices)
        return {"answer": answer, "sources": sources}

    def _filter_invoices(self, question: str, invoices: list) -> list:
        q = question.lower()

        if "duplicate" in q:
            return [inv for inv in invoices if inv.is_duplicate]

        if "invalid" in q or "failed validation" in q or "validation issue" in q:
            return [inv for inv in invoices if inv.validation_status == "invalid"]

        if "valid" in q and "invalid" not in q:
            return [inv for inv in invoices if inv.validation_status == "valid"]

        if "gstin" in q and ("missing" in q or "issue" in q):
            return [
                inv for inv in invoices
                if any("gstin" in issue.lower() for issue in (inv.validation_errors or []))
            ]

        if ("vat" in q or "trn" in q) and ("missing" in q or "issue" in q):
            return [
                inv for inv in invoices
                if any(("vat" in issue.lower() or "trn" in issue.lower()) for issue in (inv.validation_errors or []))
            ]

        if "high value" in q or "high-value" in q or "above" in q or "greater than" in q:
            threshold = self._extract_threshold(q) or 100000
            return [inv for inv in invoices if (inv.total_amount or 0) >= threshold]

        return invoices

    def _build_sources(self, invoices: list) -> list[dict]:
        sources = []
        seen = set()
        for inv in invoices:
            if inv.id in seen:
                continue
            seen.add(inv.id)
            sources.append({
                "invoice_id": inv.invoice_number or inv.id,
                "row_id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": inv.total_amount,
                "vendor": inv.vendor_name,
                "vendor_name": inv.vendor_name,
            })
            if len(sources) >= 5:
                break
        return sources

    def _extract_threshold(self, question: str) -> float | None:
        match = re.search(r"(?:above|greater than|over|more than)\s+(?:rs\.?|inr|aed|usd|\$)?\s*([\d,]+(?:\.\d+)?)", question)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    # ──────────────────────────────────────────────
    # Groq / fallback answer rendering
    # ──────────────────────────────────────────────

    def _ask_groq_about_users(self, question: str, context: str) -> str:
        prompt = f"""You are an admin assistant for an Invoice Management System.
You are answering a question about user ACCOUNTS in the system (not invoices).

User Account Data:
{context}

Question: {question}

Answer clearly and factually based only on the data above. Do not invent users,
emails, or roles that are not listed.
Answer:"""
        response = self.client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": "You are an admin assistant answering questions about user accounts."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        return response.choices[0].message.content

    def _db_fallback_user_answer(self, context: str) -> str:
        line_count = len([l for l in context.split("\n") if l.strip()])
        return (
            f"Found {line_count} user account(s):\n{context}\n\n"
            f"(Set GROQ_API_KEY in backend/.env for AI-summarized answers.)"
        )

    def _ask_groq(self, question: str, context: str) -> str:
        prompt = f"""You are a financial AI assistant for an Invoice Management System.

Invoice Data:
{context}

Question: {question}

Answer clearly and professionally. Use the invoice currency code/symbol (INR/Rs., USD/$, AED).
Answer:"""
        response = self.client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": "You are a financial invoice assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        return response.choices[0].message.content

    def _db_fallback_answer(self, question: str, invoices: list) -> str:
        totals_by_currency = {}
        for inv in invoices:
            currency = inv.currency or "INR"
            totals_by_currency[currency] = totals_by_currency.get(currency, 0.0) + (inv.total_amount or 0.0)
        totals_text = ", ".join(f"{currency} {amount:,.2f}" for currency, amount in totals_by_currency.items())
        vendors = list({inv.vendor_name for inv in invoices if inv.vendor_name})
        return (
            f"Found {len(invoices)} invoice(s). Total value: {totals_text}. "
            f"Vendors: {', '.join(vendors[:5]) if vendors else 'N/A'}. "
            f"(Set GROQ_API_KEY in backend/.env for AI-powered answers.)"
        )


rag_engine = RAGEngine()
