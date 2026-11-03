"""
FloraChain B2B — Physical Delivery Inspection & Dual Confirmation Service
Stage 3: Database-Backed Delivery Verification, Dual-Party Confirmation & Locking Engine
"""

import json
from app.services.audit_service import log_audit_event

def validate_quantities(ordered_qty, delivered_qty, sound_qty, damaged_qty):
    """
    Strict server-side mathematical validation:
    - Quantities must be non-negative whole integers (rejects floats, bools, and negatives)
    - sound_qty + damaged_qty must equal delivered_qty exactly
    - Flags mismatch between ordered and delivered counts without altering original ordered_qty
    """
    for name, val in [("Ordered", ordered_qty), ("Delivered", delivered_qty), 
                      ("Sound", sound_qty), ("Damaged", damaged_qty)]:
        # Note: In Python, isinstance(True, int) is True, so explicitly check type is int
        if type(val) is not int or val < 0:
            raise ValueError(f"{name} quantity must be a non-negative whole integer.")

    if sound_qty + damaged_qty != delivered_qty:
        raise ValueError(
            f"Quantity calculation mismatch: Sound plants ({sound_qty}) + Damaged plants ({damaged_qty}) "
            f"= {sound_qty + damaged_qty}, which does not match Delivered total ({delivered_qty})."
        )

    damage_pct = round((damaged_qty / delivered_qty) * 100.0, 2) if delivered_qty > 0 else 0.0
    has_mismatch = 1 if delivered_qty != ordered_qty else 0
    mismatch_diff = delivered_qty - ordered_qty

    return {
        "ordered_qty": ordered_qty,
        "delivered_qty": delivered_qty,
        "sound_qty": sound_qty,
        "damaged_qty": damaged_qty,
        "damage_pct": damage_pct,
        "has_mismatch": has_mismatch,
        "mismatch_diff": mismatch_diff,
        "accepted_qty": sound_qty
    }

def create_or_update_inspection(conn, order_id, actor_user, delivered_qty, sound_qty, 
                                damaged_qty, damage_notes="", ip_address="127.0.0.1"):
    """
    Creates or updates a physical arrival inspection record.
    Enforces:
    - Order existence
    - Role authorization (NURSERY role only for arrival intake)
    - Order assignment (only the assigned nursery can submit counts)
    - Rejects ordinary edits if the inspection is already locked
    - Records Nursery's initial confirmation into inspection_confirmations
    - Appends audit event to audit ledger
    """
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        raise ValueError(f"Order #{order_id} not found.")

    # 1. Server-side role authorization & ownership check
    if actor_user["role"] != "NURSERY":
        raise PermissionError("Only the assigned Nursery receiving team can record physical arrival inspections.")

    if order["nursery_user_id"] != actor_user["id"]:
        raise PermissionError(f"Unauthorized: You are not the assigned nursery for Order #{order_id}.")

    # 2. Immutability check on existing record
    existing = conn.execute("SELECT * FROM delivery_inspections WHERE order_id = ?", (order_id,)).fetchone()
    if existing and existing["is_locked"] == 1:
        raise PermissionError(f"Order #{order_id} is finalized and locked. Edits are strictly forbidden.")

    # 3. Server-side mathematical validation
    metrics = validate_quantities(order["ordered_qty"], delivered_qty, sound_qty, damaged_qty)

    before_state = dict(existing) if existing else None

    if existing:
        conn.execute(
            """UPDATE delivery_inspections
               SET delivered_qty = ?, sound_qty = ?, damaged_qty = ?, damage_pct = ?,
                   damage_notes = ?, has_mismatch = ?, mismatch_diff = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (metrics["delivered_qty"], metrics["sound_qty"], metrics["damaged_qty"],
             metrics["damage_pct"], damage_notes.strip(), metrics["has_mismatch"],
             metrics["mismatch_diff"], existing["id"])
        )
        inspection_id = existing["id"]
        event_type = "INSPECTION_UPDATED"
    else:
        cursor = conn.execute(
            """INSERT INTO delivery_inspections
               (order_id, delivered_qty, sound_qty, damaged_qty, damage_pct, damage_notes,
                has_mismatch, mismatch_diff, status, is_locked)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_SUPPLIER_CONFIRMATION', 0)""",
            (order_id, metrics["delivered_qty"], metrics["sound_qty"], metrics["damaged_qty"],
             metrics["damage_pct"], damage_notes.strip(), metrics["has_mismatch"],
             metrics["mismatch_diff"])
        )
        inspection_id = cursor.lastrowid
        event_type = "INSPECTION_CREATED"

    # 4. Automatically register Nursery's confirmation
    existing_conf = conn.execute(
        "SELECT * FROM inspection_confirmations WHERE inspection_id = ? AND party_role = 'NURSERY'",
        (inspection_id,)
    ).fetchone()
    if not existing_conf:
        conn.execute(
            """INSERT INTO inspection_confirmations (inspection_id, party_role, user_id, ip_address, signature_note)
               VALUES (?, 'NURSERY', ?, ?, ?)""",
            (inspection_id, actor_user["id"], ip_address, 
             damage_notes.strip() if damage_notes else "Physical dock inspection recorded by nursery receiving.")
        )

    # Transition order status to pending confirmation
    conn.execute(
        "UPDATE orders SET status = 'INSPECTED_PENDING_CONFIRMATION' WHERE id = ?",
        (order_id,)
    )
    conn.execute(
        "UPDATE delivery_inspections SET status = 'PENDING_SUPPLIER_CONFIRMATION' WHERE id = ?",
        (inspection_id,)
    )

    updated_inspection = conn.execute("SELECT * FROM delivery_inspections WHERE id = ?", (inspection_id,)).fetchone()
    after_state = dict(updated_inspection)

    log_audit_event(
        conn,
        event_type=event_type,
        order_id=order_id,
        actor_user_id=actor_user["id"],
        actor_role=actor_user["role"],
        before_state=before_state,
        after_state=after_state,
        justification=damage_notes.strip() or "Physical dock arrival counts recorded.",
        ip_address=ip_address
    )

    return get_inspection_details(conn, order_id)

def confirm_inspection_by_party(conn, order_id, actor_user, party_role, signature_note="", ip_address="127.0.0.1"):
    """
    Submits independent party counter-signature (NURSERY or SUPPLIER).
    Locking occurs ONLY when both independent parties have confirmed.
    
    CRITICAL SECURITY INVARIANTS:
    1. Order must exist and an initial inspection must have been recorded.
    2. Locked orders reject all further confirmation submissions.
    3. Administrators CANNOT counter-sign or satisfy independent party confirmations.
    4. Actor user role must match party_role ('NURSERY' or 'SUPPLIER').
    5. Actor user must be the assigned nursery/supplier for this wholesale order.
    6. Duplicate confirmations for the same party role are strictly rejected (409 Conflict).
    7. Atomically locks the record when both independent confirmations are in place.
    """
    # 1. Retrieve order and inspection
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        raise ValueError(f"Order #{order_id} not found.")

    inspection = conn.execute("SELECT * FROM delivery_inspections WHERE order_id = ?", (order_id,)).fetchone()
    if not inspection:
        raise ValueError(f"No delivery inspection recorded for Order #{order_id}. Physical counts must be logged first.")

    if inspection["is_locked"] == 1:
        raise PermissionError(f"Order #{order_id} is already permanently locked and finalized.")

    # 2. Normalize and validate party role
    normalized_party = (party_role or '').upper().strip()
    if normalized_party not in ('NURSERY', 'SUPPLIER'):
        raise ValueError(f"Invalid confirmation party '{party_role}'. Must be NURSERY or SUPPLIER.")

    # 3. Administrator restriction
    if actor_user["role"] == "ADMIN":
        raise PermissionError("Security Violation: Administrators cannot impersonate either party or satisfy independent delivery confirmations.")

    # 4. Role & Assignment authorization check
    if normalized_party == "NURSERY":
        if actor_user["role"] != "NURSERY":
            raise PermissionError("Forbidden: User must have NURSERY role to submit nursery confirmation.")
        if order["nursery_user_id"] != actor_user["id"]:
            raise PermissionError(f"Unauthorized: You are not the assigned nursery for Order #{order_id}.")
    elif normalized_party == "SUPPLIER":
        if actor_user["role"] != "SUPPLIER":
            raise PermissionError("Forbidden: User must have SUPPLIER role to submit supplier confirmation.")
        if order["supplier_user_id"] != actor_user["id"]:
            raise PermissionError(f"Unauthorized: You are not the assigned supplier for Order #{order_id}.")

    # 5. Check for duplicate confirmation by this party
    existing_conf = conn.execute(
        "SELECT * FROM inspection_confirmations WHERE inspection_id = ? AND party_role = ?",
        (inspection["id"], normalized_party)
    ).fetchone()
    if existing_conf:
        raise ValueError(f"Party '{normalized_party}' has already confirmed Order #{order_id} on {existing_conf['confirmed_at']}.")

    # 6. Insert counter-signature confirmation
    conn.execute(
        """INSERT INTO inspection_confirmations (inspection_id, party_role, user_id, ip_address, signature_note)
           VALUES (?, ?, ?, ?, ?)""",
        (inspection["id"], normalized_party, actor_user["id"], ip_address, signature_note.strip())
    )

    log_audit_event(
        conn,
        event_type=f"{normalized_party}_CONFIRMED",
        order_id=order_id,
        actor_user_id=actor_user["id"],
        actor_role=actor_user["role"],
        before_state=None,
        after_state={"confirmed_party": normalized_party, "signature_note": signature_note.strip()},
        justification=signature_note.strip() or f"Counter-signature submitted by {normalized_party}.",
        ip_address=ip_address
    )

    # 7. Check if BOTH independent parties have confirmed
    confirmations = conn.execute(
        "SELECT party_role FROM inspection_confirmations WHERE inspection_id = ?",
        (inspection["id"],)
    ).fetchall()
    confirmed_roles = {c["party_role"] for c in confirmations}

    both_confirmed = ("NURSERY" in confirmed_roles and "SUPPLIER" in confirmed_roles)

    if both_confirmed:
        # ATOMIC SERVER-SIDE LOCK
        conn.execute(
            """UPDATE delivery_inspections 
               SET is_locked = 1, status = 'LOCKED_VERIFIED', locked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (inspection["id"],)
        )
        conn.execute(
            "UPDATE orders SET status = 'LOCKED_VERIFIED' WHERE id = ?",
            (order_id,)
        )

        locked_inspection = conn.execute("SELECT * FROM delivery_inspections WHERE id = ?", (inspection["id"],)).fetchone()

        log_audit_event(
            conn,
            event_type="ORDER_LOCKED",
            order_id=order_id,
            actor_user_id=actor_user["id"],
            actor_role="SYSTEM_DUAL_LOCK",
            before_state=dict(inspection),
            after_state=dict(locked_inspection),
            justification="Dual confirmation finalized: Both independent parties counter-signed. Record permanently locked.",
            ip_address=ip_address
        )

    return get_inspection_details(conn, order_id)

def get_inspection_details(conn, order_id):
    """
    Returns full order and inspection status including dual confirmation signatures.
    """
    order = conn.execute(
        """SELECT o.*, 
                  s.username as supplier_username, s.business_name as supplier_name,
                  n.username as nursery_username, n.business_name as nursery_name
           FROM orders o
           JOIN users s ON o.supplier_user_id = s.id
           JOIN users n ON o.nursery_user_id = n.id
           WHERE o.id = ?""",
        (order_id,)
    ).fetchone()
    if not order:
        return None

    inspection = conn.execute("SELECT * FROM delivery_inspections WHERE order_id = ?", (order_id,)).fetchone()
    
    confirmations = []
    if inspection:
        conf_rows = conn.execute(
            """SELECT c.*, u.username, u.business_name
               FROM inspection_confirmations c
               JOIN users u ON c.user_id = u.id
               WHERE c.inspection_id = ?
               ORDER BY c.confirmed_at ASC""",
            (inspection["id"],)
        ).fetchall()
        for c in conf_rows:
            confirmations.append({
                "party_role": c["party_role"],
                "confirmed_at": c["confirmed_at"],
                "user_id": c["user_id"],
                "user_name": c["username"],
                "business_name": c["business_name"],
                "signature_note": c["signature_note"]
            })

    confirmed_roles = {c["party_role"] for c in confirmations}

    return {
        "order": dict(order),
        "inspection": dict(inspection) if inspection else None,
        "confirmations": confirmations,
        "nursery_confirmed": "NURSERY" in confirmed_roles,
        "supplier_confirmed": "SUPPLIER" in confirmed_roles,
        "is_locked": bool(inspection["is_locked"]) if inspection else False,
        "status": inspection["status"] if inspection else order["status"]
    }

def import_localstorage_draft(conn, draft_data, actor_user, ip_address="127.0.0.1"):
    """
    Safely imports client-side localStorage draft data.
    SECURITY INVARIANT: Client drafts are treated as untrusted legacy data.
    They are NEVER imported as pre-locked or pre-verified records.
    They are imported as 'DRAFT' (is_locked = 0) and require independent counter-signatures on backend.
    """
    order_id = draft_data.get("orderId")
    if not order_id:
        raise ValueError("Missing orderId in import payload.")

    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        raise ValueError(f"Order #{order_id} does not exist on platform.")

    delivered_qty = int(draft_data.get("deliveredQty", order["ordered_qty"]))
    sound_qty = int(draft_data.get("soundQty", order["ordered_qty"]))
    damaged_qty = int(draft_data.get("damagedQty", 0))
    damage_notes = str(draft_data.get("damageNotes", ""))

    metrics = validate_quantities(order["ordered_qty"], delivered_qty, sound_qty, damaged_qty)

    existing = conn.execute("SELECT * FROM delivery_inspections WHERE order_id = ?", (order_id,)).fetchone()
    if existing and existing["is_locked"] == 1:
        # Existing locked backend record is strictly protected from overwrite by client draft
        return get_inspection_details(conn, order_id)

    if existing:
        conn.execute(
            """UPDATE delivery_inspections
               SET delivered_qty = ?, sound_qty = ?, damaged_qty = ?, damage_pct = ?,
                   damage_notes = ?, has_mismatch = ?, mismatch_diff = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (metrics["delivered_qty"], metrics["sound_qty"], metrics["damaged_qty"],
             metrics["damage_pct"], damage_notes, metrics["has_mismatch"],
             metrics["mismatch_diff"], existing["id"])
        )
    else:
        conn.execute(
            """INSERT INTO delivery_inspections
               (order_id, delivered_qty, sound_qty, damaged_qty, damage_pct, damage_notes,
                has_mismatch, mismatch_diff, status, is_locked)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', 0)""",
            (order_id, metrics["delivered_qty"], metrics["sound_qty"], metrics["damaged_qty"],
             metrics["damage_pct"], damage_notes, metrics["has_mismatch"],
             metrics["mismatch_diff"])
        )

    log_audit_event(
        conn,
        event_type="LOCALSTORAGE_IMPORT",
        order_id=order_id,
        actor_user_id=actor_user["id"],
        actor_role=actor_user["role"],
        before_state=None,
        after_state=metrics,
        justification="Imported unverified client-side localStorage snapshot (requires independent counter-signatures; untrusted).",
        ip_address=ip_address
    )

    return get_inspection_details(conn, order_id)


def approve_correction(conn, corr_id, actor_user, ip_address="127.0.0.1"):
    """
    Approves an administrative correction for an inspection record.
    Updates the delivery_inspections quantities and logs an audit event.
    """
    if actor_user["role"] != "ADMIN":
        raise PermissionError("Only administrators can approve inspection corrections.")

    corr = conn.execute(
        """SELECT c.*, di.order_id, di.sound_qty as current_sound, di.damaged_qty as current_damaged, di.delivered_qty
           FROM inspection_corrections c
           JOIN delivery_inspections di ON c.inspection_id = di.id
           WHERE c.id = ?""",
        (corr_id,)
    ).fetchone()

    if not corr:
        raise ValueError(f"Correction #{corr_id} not found.")

    if corr["status"] != "PENDING":
        raise ValueError(f"Correction #{corr_id} has already been resolved with status '{corr['status']}'.")

    delivered_qty = corr["delivered_qty"]
    new_sound = corr["corrected_sound_qty"]
    new_damaged = corr["corrected_damaged_qty"]
    new_pct = round((new_damaged / delivered_qty) * 100.0, 2) if delivered_qty > 0 else 0.0

    conn.execute(
        """UPDATE inspection_corrections
           SET status = 'APPROVED', approved_by = ?, resolved_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (actor_user["id"], corr_id)
    )

    conn.execute(
        """UPDATE delivery_inspections
           SET sound_qty = ?, damaged_qty = ?, damage_pct = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (new_sound, new_damaged, new_pct, corr["inspection_id"])
    )

    before_state = {
        "sound_qty": corr["current_sound"],
        "damaged_qty": corr["current_damaged"]
    }
    after_state = {
        "sound_qty": new_sound,
        "damaged_qty": new_damaged,
        "damage_pct": new_pct
    }

    log_audit_event(
        conn,
        event_type="CORRECTION_APPROVED",
        order_id=corr["order_id"],
        actor_user_id=actor_user["id"],
        actor_role=actor_user["role"],
        before_state=before_state,
        after_state=after_state,
        justification=f"Admin approved formal correction #{corr_id}: {corr['reason']}",
        ip_address=ip_address
    )

    return {
        "correction_id": corr_id,
        "order_id": corr["order_id"],
        "status": "APPROVED",
        "corrected_sound_qty": new_sound,
        "corrected_damaged_qty": new_damaged
    }
