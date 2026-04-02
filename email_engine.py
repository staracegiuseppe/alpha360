"""
Alpha360 — Email Digest Engine
================================
Genera e invia digest HTML+plain-text.
Deduplica hash-based, change detection, retry con backoff.
Riusa Gmail App Password.
"""

import hashlib
import logging
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

from engine import ScoringEngine

logger = logging.getLogger("alpha360.email")


class EmailDigestEngine:

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.last_hash: Optional[str] = None
        self.last_analyses: Optional[List] = None
        self.last_sent: Optional[str] = None
        self.send_count = 0
        self.error_count = 0
        self.last_error: Optional[str] = None

    def get_status(self) -> dict:
        return {
            "enabled": self.config.get("enabled", False),
            "last_sent": self.last_sent,
            "last_hash": self.last_hash,
            "send_count": self.send_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "recipients": self.config.get("recipients", []),
            "mode": self.config.get("mode", "full"),
        }

    def send_digest(self, analyses: list, force: bool = False) -> dict:
        if not self.config.get("enabled") and not force:
            return {"status": "disabled"}

        h = ScoringEngine.digest_hash(analyses)
        if h == self.last_hash and not force and not self.config.get("always_send"):
            return {"status": "skipped", "reason": "duplicate", "hash": h}

        changes = ScoringEngine.detect_changes(analyses, self.last_analyses or [])
        ts = datetime.now().isoformat()
        subj = self._subject(analyses, ts)
        html = self._html(analyses, changes, ts)
        text = self._text(analyses, changes, ts)

        result = self._send(subj, html, text)

        if result["status"] == "sent":
            self.last_hash = h
            self.last_analyses = analyses
            self.last_sent = ts
            self.send_count += 1
        else:
            self.error_count += 1
            self.last_error = result.get("error")

        return {**result, "hash": h, "changes": len(changes), "timestamp": ts}

    def preview(self, analyses: list) -> dict:
        ts = datetime.now().isoformat()
        changes = ScoringEngine.detect_changes(analyses, self.last_analyses or [])
        h = ScoringEngine.digest_hash(analyses)
        return {
            "subject": self._subject(analyses, ts),
            "html": self._html(analyses, changes, ts),
            "text": self._text(analyses, changes, ts),
            "hash": h,
            "is_duplicate": h == self.last_hash,
            "changes": changes,
        }

    def _subject(self, analyses, ts):
        buys = sum(1 for a in analyses if a.get("final_rating") == "BUY")
        sells = sum(1 for a in analyses if a.get("final_rating") == "SELL")
        strong = sum(1 for a in analyses if a.get("convergence_state") == "STRONG")
        dt = datetime.fromisoformat(ts)
        return f"Alpha360 {dt.strftime('%d/%m %H:%M')} | {buys}B {sells}S | {strong} Strong"

    def _html(self, analyses, changes, ts):
        dt = datetime.fromisoformat(ts)
        buys = sorted([a for a in analyses if a.get("final_rating") == "BUY"],
                       key=lambda x: x.get("confidence", 0), reverse=True)
        sells = sorted([a for a in analyses if a.get("final_rating") == "SELL"],
                        key=lambda x: x.get("confidence", 0), reverse=True)
        watches = [a for a in analyses if a.get("final_rating") == "WATCH"]
        strong = [a for a in analyses if a.get("convergence_state") == "STRONG"]
        div = [a for a in analyses if a.get("convergence_state") == "DIVERGENT"]

        rc = lambda r: {"BUY":"#22c55e","SELL":"#ef4444","WATCH":"#f59e0b"}.get(r,"#888")

        def row(a):
            chg = a.get("change_pct", 0)
            return f'''<tr style="border-bottom:1px solid #1e293b">
              <td style="padding:6px 8px;font-weight:700;color:#e2e8f0;font-family:monospace">{a["symbol"]}</td>
              <td style="padding:6px 8px"><span style="background:{rc(a.get("final_rating",""))};color:#000;padding:2px 6px;border-radius:3px;font-size:11px;font-weight:700">{a.get("final_rating","")}</span></td>
              <td style="padding:6px 8px;color:#94a3b8;text-align:center;font-family:monospace">{a.get("confidence",0)}%</td>
              <td style="padding:6px 8px;color:#64748b;font-size:11px">{a.get("convergence_state","")}</td>
              <td style="padding:6px 8px;color:{"#22c55e" if chg>=0 else "#ef4444"};font-family:monospace">{("+" if chg>=0 else "")}{chg:.2f}%</td>
              <td style="padding:6px 8px;color:#64748b;font-family:monospace">{a.get("scores",{}).get("final_score",0)}</td>
            </tr>'''

        def tbl(items):
            if not items: return '<p style="color:#475569;font-style:italic">Nessuno</p>'
            hdr = '<table style="width:100%;border-collapse:collapse"><thead><tr style="border-bottom:2px solid #334155">'
            for h in ["TICKER","RATING","CONF","CONV","CHG%","SCORE"]:
                hdr += f'<th style="text-align:left;padding:4px 8px;color:#64748b;font-size:10px">{h}</th>'
            hdr += '</tr></thead><tbody>'
            return hdr + ''.join(row(a) for a in items) + '</tbody></table>'

        ch = ""
        if changes:
            items = ''.join(f'<p style="margin:3px 0;color:#fde68a;font-size:12px"><b>{c["symbol"]}</b>: {c["type"]} — {c["detail"]}</p>' for c in changes)
            ch = f'<div style="background:#1e1a00;border:1px solid #854d0e;border-radius:6px;padding:12px;margin-bottom:12px"><h3 style="margin:0 0 6px;color:#fbbf24;font-size:12px">⚡ VARIAZIONI</h3>{items}</div>'

        sh = ""
        if strong:
            items = ''.join(f'<p style="margin:2px 0;color:#86efac;font-size:12px"><b>{a["symbol"]}</b> {a.get("final_rating","")} Conf:{a.get("confidence",0)}%</p>' for a in strong)
            sh = f'<div style="background:#001a0a;border:1px solid #166534;border-radius:6px;padding:12px;margin-bottom:12px"><h3 style="margin:0 0 6px;color:#4ade80;font-size:12px">🎯 FORTE CONVERGENZA</h3>{items}</div>'

        dh = ""
        if div:
            items = ''.join(f'<p style="margin:2px 0;color:#fca5a5;font-size:12px"><b>{a["symbol"]}</b> T:{a.get("scores",{}).get("technical",0)} SM:{a.get("scores",{}).get("smart_money",0)}</p>' for a in div)
            dh = f'<div style="background:#1a0000;border:1px solid #991b1b;border-radius:6px;padding:12px;margin-bottom:12px"><h3 style="margin:0 0 6px;color:#f87171;font-size:12px">⚠ DIVERGENZA</h3>{items}</div>'

        digest_hash = ScoringEngine.digest_hash(analyses)

        return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0f1a;font-family:-apple-system,monospace">
<div style="max-width:640px;margin:0 auto;padding:16px">
  <div style="background:linear-gradient(135deg,#0f172a,#1e293b);border:1px solid #334155;border-radius:8px;padding:16px;margin-bottom:12px">
    <h1 style="margin:0;color:#f1f5f9;font-size:17px">Alpha360 — Digest Operativo</h1>
    <p style="margin:4px 0 0;color:#64748b;font-size:11px">{dt.strftime("%d/%m/%Y %H:%M")} | {len(analyses)} titoli</p>
  </div>
  {ch}
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:10px">
    <h3 style="margin:0 0 6px;color:#22c55e;font-size:12px">🟢 BUY ({len(buys)})</h3>{tbl(buys)}</div>
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:10px">
    <h3 style="margin:0 0 6px;color:#f59e0b;font-size:12px">🟡 WATCH ({len(watches)})</h3>{tbl(watches)}</div>
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:10px">
    <h3 style="margin:0 0 6px;color:#ef4444;font-size:12px">🔴 SELL ({len(sells)})</h3>{tbl(sells)}</div>
  {sh}{dh}
  <div style="text-align:center;padding:14px 0;border-top:1px solid #1e293b">
    <p style="color:#475569;font-size:10px;margin:0">Alpha360 — HAOS Add-on | Hash: {digest_hash}</p>
  </div>
</div></body></html>'''

    def _text(self, analyses, changes, ts):
        dt = datetime.fromisoformat(ts)
        lines = [f"ALPHA360 DIGEST — {dt.strftime('%d/%m/%Y %H:%M')}", "=" * 50, ""]
        if changes:
            lines.append("VARIAZIONI:")
            for c in changes: lines.append(f"  {c['symbol']}: {c['type']} — {c['detail']}")
            lines.append("")
        for label, rating in [("BUY", "BUY"), ("WATCH", "WATCH"), ("SELL", "SELL")]:
            items = [a for a in analyses if a.get("final_rating") == rating]
            lines.append(f"{label} ({len(items)}):")
            for a in items:
                lines.append(f"  {a['symbol']:<8} Conf:{a.get('confidence',0)}% Conv:{a.get('convergence_state','')} Score:{a.get('scores',{}).get('final_score',0)}")
            lines.append("")
        return "\n".join(lines)

    def _send(self, subject, html, text) -> dict:
        user = self.config.get("smtp_user", "")
        pwd = self.config.get("smtp_password", "")
        recipients = self.config.get("recipients", [])
        sender = self.config.get("sender", user)

        if not user or not pwd:
            return {"status": "error", "error": "SMTP non configurato"}
        if not recipients:
            return {"status": "error", "error": "Nessun destinatario"}

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        for attempt in range(3):
            try:
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
                    s.ehlo(); s.starttls(); s.ehlo()
                    s.login(user, pwd)
                    s.sendmail(sender, recipients, msg.as_string())
                return {"status": "sent", "recipients": recipients}
            except Exception as e:
                logger.warning(f"[Email] attempt {attempt+1}: {e}")
                if attempt < 2: time.sleep(2 ** attempt)
        return {"status": "error", "error": str(e)}
