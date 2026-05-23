import sqlite3
import os
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="DNA Data Storage Unit - API Server")

# Enable CORS for local cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Vercel serverless environment has a read-only filesystem except for /tmp
# Write DB to /tmp to prevent read-only filesystem errors
DB_PATH = "/tmp/lab_inventory.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL UNIQUE,
            sequence TEXT NOT NULL,
            original_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Initialize database
init_db()

class VialCreate(BaseModel):
    label: str
    sequence: str
    original_text: Optional[str] = None

@app.post("/api/vials", status_code=status.HTTP_201_CREATED)
async def create_vial(vial: VialCreate):
    label = vial.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="Vial label cannot be empty.")
    
    sequence = vial.sequence.strip().upper()
    if not sequence:
        raise HTTPException(status_code=400, detail="DNA sequence cannot be empty.")
    
    for char in sequence:
        if char not in ['A', 'T', 'C', 'G']:
            raise HTTPException(status_code=400, detail=f"Invalid character '{char}' in DNA sequence. Only A, T, C, G are allowed.")
            
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO vials (label, sequence, original_text) VALUES (?, ?, ?)",
            (label, sequence, vial.original_text)
        )
        conn.commit()
        vial_id = cursor.lastrowid
        return {"id": vial_id, "label": label, "message": "Vial successfully stored in virtual database."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"Vial label '{label}' already exists in inventory database.")
    finally:
        conn.close()

@app.get("/api/vials")
async def get_all_vials():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, label, length(sequence) as length, original_text, created_at FROM vials ORDER BY created_at DESC")
    rows = cursor.fetchall()
    vials = []
    for row in rows:
        vials.append({
            "id": row["id"],
            "label": row["label"],
            "length": row["length"],
            "original_text": row["original_text"],
            "created_at": row["created_at"]
        })
    conn.close()
    return vials

@app.get("/api/vials/{label}")
async def get_vial(label: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, label, sequence, original_text, created_at FROM vials WHERE label = ?", (label,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Vial with label '{label}' not found.")
    return {
        "id": row["id"],
        "label": row["label"],
        "sequence": row["sequence"],
        "original_text": row["original_text"],
        "created_at": row["created_at"]
    }

@app.delete("/api/vials/{vial_id}")
async def delete_vial(vial_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vials WHERE id = ?", (vial_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Vial with ID {vial_id} not found in database.")
    return {"message": f"Vial with ID {vial_id} deleted successfully."}
