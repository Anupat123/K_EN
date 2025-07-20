from flask import Flask, render_template, request, redirect, url_for 
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
DATA_FILE = "data.json"
SHEET_ID = "1N3KDfWjAEEob4pVzZnZQaCYyH54pODdNcNYzu0M_6Wk"  # ใส่ Sheet ID ของคุณ

def read_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"orders": [], "deleted_orders": []}

def write_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("Environment variable GOOGLE_CREDENTIALS not found.")

    try:
        creds_dict = json.loads(creds_json)

        # แก้ไข private_key ที่มักจะถูก escape "\n" ให้กลับเป็นจริง
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception as e:
        raise Exception(f"Failed to connect to Google Sheet: {e}")

def append_to_sheet(order):
    sheet = get_sheet()
    row = [
        order["id"],
        order["corn_qty"],
        order["drinks"]["drink1"],
        order["drinks"]["drink2"],
        order["drinks"]["drink3"],
        order["drinks"]["drink4"],
        order["drinks"]["drink5"],
        order["drinks"]["drink6"],
        order["total_price"],
        order["payment_method"]
    ]
    sheet.append_row(row)

def delete_from_sheet(order_id):
    sheet = get_sheet()
    records = sheet.get_all_records()
    for idx, row in enumerate(records):
        if int(row.get("id", -1)) == order_id:
            sheet.delete_rows(idx + 2)
            break

drink_names = [
    "ชานมไข่มุก",
    "โกโก้เย็น",
    "ชาเขียว",
    "นมชมพู",
    "โอเลี้ยง",
    "น้ำเปล่า"
]

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    data = read_data()
    orders = data.get('orders', [])
    deleted_orders = data.get('deleted_orders', [])
    total_orders = len(orders)
    total_revenue = sum(order['total_price'] for order in orders)
    return render_template("dashboard.html",
                           orders=orders,
                           deleted_orders=deleted_orders,
                           total_orders=total_orders,
                           total_revenue=total_revenue,
                           drink_names=drink_names)

@app.route('/order', methods=['GET', 'POST'])
def order():
    if request.method == 'POST':
        corn_qty = int(request.form.get('corn_qty', 0))
        drinks = []
        total_price = corn_qty * 29

        drinks_qty = {}
        for i in range(1, 7):
            qty = int(request.form.get(f'drink{i}', 0))
            drinks.append({
                "name": drink_names[i-1], 
                "qty": qty, 
                "price": qty * 20
            })
            drinks_qty[f'drink{i}'] = qty
            total_price += qty * 20

        return render_template('payment.html',
                               corn_qty=corn_qty,
                               drinks=drinks,
                               drinks_qty=drinks_qty,
                               total_price=total_price)
    return render_template('order.html', drink_names=drink_names)

@app.route('/confirm', methods=['POST'])
def confirm():
    corn_qty = int(request.form['corn_qty'])
    total_price = int(request.form['total_price'])
    payment_method = request.form.get('payment_method', 'unknown')

    drinks = {}
    for i in range(1, 7):
        qty = int(request.form.get(f'drink{i}', 0))
        drinks[f'drink{i}'] = qty

    data = read_data()
    orders = data.get('orders', [])
    new_id = max([order['id'] for order in orders], default=0) + 1

    new_order = {
        "id": new_id,
        "corn_qty": corn_qty,
        "drinks": drinks,
        "total_price": total_price,
        "payment_method": payment_method
    }

    orders.append(new_order)
    data['orders'] = orders
    write_data(data)

    append_to_sheet(new_order)
    return redirect(url_for('dashboard'))

@app.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    reason = request.form.get('reason', '').strip()

    data = read_data()
    orders = data.get('orders', [])
    deleted_orders = data.get('deleted_orders', [])

    for order in orders:
        if order['id'] == order_id:
            order['delete_reason'] = reason
            deleted_orders.append(order)
            orders.remove(order)
            break

    data['orders'] = orders
    data['deleted_orders'] = deleted_orders
    write_data(data)

    delete_from_sheet(order_id)
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
