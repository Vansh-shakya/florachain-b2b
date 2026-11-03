"""
FloraChain B2B — Append-Only Immutable Audit Service
"""

import json

def log_audit_event(conn, event_type, order_id, actor_user_id, actor_role, 
                    before_state=None, after_state=None, justification="", ip_address="127.0.0.1"):
    """
    Appends an immutable audit event to the ledger.
    """
    before_json = json.dumps(before_state) if before_state is not None else None
    after_json = json.dumps(after_state) if after_state is not None else "{}"

    cursor = conn.execute(
        """INSERT INTO audit_events 
           (event_type, order_id, actor_user_id, actor_role, before_state_json, after_state_json, justification, ip_address)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_type, order_id, actor_user_id, actor_role, before_json, after_json, justification, ip_address)
    )
    return cursor.lastrowid

def get_audit_trail_for_order(conn, order_id):
    """
    Retrieves the chronological audit log for a specific order.
    """
    rows = conn.execute(
        """SELECT a.*, u.username as actor_username, u.business_name as actor_business
           FROM audit_events a
           LEFT JOIN users u ON a.actor_user_id = u.id
           WHERE a.order_id = ?
           ORDER BY a.created_at ASC, a.id ASC""",
        (order_id,)
    ).fetchall()

    events = []
    for r in rows:
        before_state = None
        if r["before_state_json"]:
            try:
                before_state = json.loads(r["before_state_json"])
            except Exception:
                before_state = {"raw": str(r["before_state_json"])}

        after_state = {}
        if r["after_state_json"]:
            try:
                after_state = json.loads(r["after_state_json"])
            except Exception:
                after_state = {"raw": str(r["after_state_json"])}

        events.append({
            "id": r["id"],
            "event_type": r["event_type"],
            "order_id": r["order_id"],
            "actor_user_id": r["actor_user_id"],
            "actor_role": r["actor_role"],
            "actor_username": r["actor_username"] or "SYSTEM",
            "actor_business": r["actor_business"] or "Platform Core",
            "before_state": before_state,
            "after_state": after_state,
            "justification": r["justification"],
            "ip_address": r["ip_address"],
            "created_at": r["created_at"]
        })
    return events
