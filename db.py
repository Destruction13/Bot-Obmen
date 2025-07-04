import sqlite3
from datetime import datetime
from typing import Any, List, Optional, Tuple, Dict
import logging

DB_NAME = 'shifts.db'


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS shifts (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER NOT NULL,
                   username TEXT,
                   start_time TEXT NOT NULL,
                   end_time TEXT NOT NULL,
                   status TEXT NOT NULL,
                   offered_to_user_id INTEGER,
                   offered_by_user_id INTEGER
               )'''
        )
        conn.commit()


def add_shift(user_id: int, username: str, start: datetime, end: datetime, status: str = 'active', offered_to: Optional[int] = None, offered_by: Optional[int] = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            'INSERT INTO shifts (user_id, username, start_time, end_time, status, offered_to_user_id, offered_by_user_id)'
            ' VALUES (?, ?, ?, ?, ?, ?, ?)',
            (user_id, username, start.isoformat(), end.isoformat(), status, offered_to, offered_by)
        )
        conn.commit()
        return cur.lastrowid


def list_active_shifts(exclude_user_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.execute(
            'SELECT * FROM shifts WHERE status = "active" AND user_id != ? ORDER BY start_time',
            (exclude_user_id,)
        )
        columns = [c[0] for c in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def list_user_shifts(user_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.execute('SELECT * FROM shifts WHERE user_id = ? ORDER BY start_time', (user_id,))
        columns = [c[0] for c in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_shift(shift_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.execute('SELECT * FROM shifts WHERE id = ?', (shift_id,))
        row = cur.fetchone()
        if row:
            columns = [c[0] for c in cur.description]
            return dict(zip(columns, row))
    return None


def delete_shift(shift_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute('DELETE FROM shifts WHERE id = ? AND user_id = ?', (shift_id, user_id))
        conn.commit()
        return cur.rowcount > 0


def offer_shift(target_shift_id: int, offered_user_id: int, offered_username: str, start: datetime, end: datetime) -> Optional[int]:
    target = get_shift(target_shift_id)
    if not target or target['status'] != 'active' or target['user_id'] == offered_user_id:
        return None
    # update target shift status
    with get_connection() as conn:
        conn.execute(
            'UPDATE shifts SET status = "offered", offered_to_user_id = ?, offered_by_user_id = ? WHERE id = ?',
            (target['user_id'], offered_user_id, target_shift_id)
        )
        conn.commit()
    offer_id = add_shift(offered_user_id, offered_username, start, end, status='offered', offered_to=target['user_id'], offered_by=offered_user_id)
    return offer_id


def approve_offer(offer_shift_id: int, approver_user_id: int) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    offer = get_shift(offer_shift_id)
    if not offer or offer['status'] != 'offered' or offer['offered_to_user_id'] != approver_user_id:
        return None
    # find target shift
    with get_connection() as conn:
        cur = conn.execute(
            'SELECT * FROM shifts WHERE user_id = ? AND offered_by_user_id = ? AND status = "offered"',
            (approver_user_id, offer['offered_by_user_id'])
        )
        target_row = cur.fetchone()
        if not target_row:
            return None
        columns = [c[0] for c in cur.description]
        target = dict(zip(columns, target_row))
        conn.execute('UPDATE shifts SET status = "confirmed" WHERE id IN (?, ?)', (offer_shift_id, target['id']))
        conn.commit()
    return offer, target
