from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3
import pandas as pd
import os
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "steez.db")

app = FastAPI(title="Steez Sales System")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------- DATABASE ----------------

def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier TEXT,
        party TEXT,
        date TEXT,
        work_type TEXT,
        completion_percent REAL,
        quotation_no TEXT,
        po_no TEXT,
        invoice_no TEXT,
        invoice_total REAL,
        amount_paid REAL,
        outstanding REAL,
        status TEXT,
        profit REAL
    )
    """)

    conn.commit()
    conn.close()

init_db()


SUPPLIERS = ["KONE", "Walk-In", "Other"]

PARTIES = [
    "SAB MALTINGS",
    "BOUTIQUE HOTEL ORMONDE",
    "THE EMERALDS",
    "SLIM HOSPITALITY-FRB",
    "LUCID SANDOWN",
    "THE VERGE SHOPPING CENTER",
    "THE MELROSE"
]

WORK_TYPES = ["Fycor", "Quality", "Lifts", "Dismantling", "Installation"]


class Sale(BaseModel):
    supplier: str
    party: str
    date: str
    work_type: str
    completion_percent: float
    quotation_no: str
    po_no: str
    invoice_no: str
    invoice_total: float
    amount_paid: float


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "suppliers": SUPPLIERS,
        "parties": PARTIES,
        "work_types": WORK_TYPES
    })


# ---------------- CREATE ----------------

@app.post("/record-sale")
def record_sale(sale: Sale):
    return save_sale(sale)


# ---------------- UPDATE ----------------

@app.put("/update-sale/{sale_id}")
def update_sale(sale_id: int, sale: Sale):
    return save_sale(sale, sale_id)


def save_sale(sale: Sale, sale_id=None):

    outstanding = sale.invoice_total - sale.amount_paid

    if outstanding == 0:
        status = "Paid"
    elif sale.amount_paid > 0:
        status = "Partial"
    else:
        status = "Unpaid"

    profit = sale.amount_paid

    conn = get_conn()
    c = conn.cursor()

    if sale_id:
        c.execute("""
        UPDATE sales SET
        supplier=?, party=?, date=?, work_type=?,
        completion_percent=?, quotation_no=?, po_no=?,
        invoice_no=?, invoice_total=?, amount_paid=?,
        outstanding=?, status=?, profit=?
        WHERE id=?
        """, (
            sale.supplier, sale.party, sale.date, sale.work_type,
            sale.completion_percent, sale.quotation_no, sale.po_no,
            sale.invoice_no, sale.invoice_total, sale.amount_paid,
            outstanding, status, profit, sale_id
        ))
    else:
        c.execute("""
        INSERT INTO sales (
        supplier, party, date, work_type,
        completion_percent, quotation_no, po_no,
        invoice_no, invoice_total, amount_paid,
        outstanding, status, profit
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sale.supplier, sale.party, sale.date, sale.work_type,
            sale.completion_percent, sale.quotation_no, sale.po_no,
            sale.invoice_no, sale.invoice_total, sale.amount_paid,
            outstanding, status, profit
        ))

    conn.commit()
    conn.close()

    return {
        "outstanding": round(outstanding, 2),
        "status": status,
        "profit": round(profit, 2)
    }


@app.get("/sales")
def get_sales():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM sales ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.delete("/delete-sale/{sale_id}")
def delete_sale(sale_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM sales WHERE id=?", (sale_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}


@app.get("/dashboard-yearly")
def dashboard():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM sales", conn)
    conn.close()

    if df.empty:
        return []

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["year"] = df["date"].dt.year

    yearly = df.groupby("year").agg({
        "invoice_total": "sum",
        "amount_paid": "sum",
        "outstanding": "sum",
        "profit": "sum"
    }).reset_index()

    return yearly.to_dict(orient="records")


@app.get("/export-excel")
def export_excel():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM sales", conn)
    conn.close()

    path = os.path.join(BASE_DIR, "steez_export.xlsx")
    df.to_excel(path, index=False)

    return FileResponse(path, filename="steez_export.xlsx")



