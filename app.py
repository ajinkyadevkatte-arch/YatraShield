from flask import Flask, render_template, request, jsonify, send_file
import requests
import qrcode
import os
import qrcode.image.svg 
import io  # NAYA ADDED: Memory me image process karne ke liye

app = Flask(__name__)

# Ensure QR code and uploads directories exist (Ab inki itni zarurat nahi hai, par purana logic break na ho isliye rakha hai)
os.makedirs(os.path.join('static', 'qrcodes'), exist_ok=True)
os.makedirs(os.path.join('static', 'uploads'), exist_ok=True) # Naya folder images ke liye

# ☁️ SUPABASE CLOUD REST API SETUP ☁️
SUPABASE_URL = "https://yxzsrdenjpecyyenwnxf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl4enNyZGVuanBlY3l5ZW53bnhmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMzMjM2MjMsImV4cCI6MjA4ODg5OTYyM30.7S3A3iJmUrH3JCrf23v-hmQbRAxe-3a7-48CgWiGke4"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

@app.route('/')
def home():
    return render_template('index.html')


# ========================================================
# 🔥 NAYA FUNCTION: Seedha Supabase Cloud Storage me file dalne ke liye 🔥
# ========================================================
def upload_to_supabase(file_bytes, file_name, content_type):
    # 'yatra_assets' bucket me file upload kar rahe hain
    url = f"{SUPABASE_URL}/storage/v1/object/yatra_assets/{file_name}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type,
        "x-upsert": "true"  # Update karne pe purani photo replace ho jayegi
    }
    res = requests.post(url, headers=headers, data=file_bytes)
    
    if res.status_code in [200, 201]:
        # Upload hone ke baad seedha Public Link return karega
        return f"{SUPABASE_URL}/storage/v1/object/public/yatra_assets/{file_name}"
    else:
        print("Supabase Upload Error:", res.text)
        return None
# ========================================================


# 1. API - Cloud me Data Save (Ya Update) karne ke liye
@app.route('/api/add_passenger', methods=['POST'])
def add_passenger():
    # Ab JSON nahi, Form data aayega kyunki file upload ho rahi hai
    p_id = request.form.get('id') 
    pnr = request.form.get('pnr')

    if not pnr:
        return jsonify({"error": "PNR is required"}), 400

    base_url = request.host_url 
    qr_data = f"{base_url}p/{pnr}" 
    
    # --- NAYA QR GENERATION (SEEDHA CLOUD ME) ---
    
    # PNG QR
    qr_img = qrcode.make(qr_data)
    img_io = io.BytesIO()
    qr_img.save(img_io, 'PNG')
    img_bytes = img_io.getvalue()
    qr_png_url = upload_to_supabase(img_bytes, f"qrcodes/qr_{pnr}.png", "image/png")

    # SVG QR
    factory = qrcode.image.svg.SvgImage
    qr_svg_img = qrcode.make(qr_data, image_factory=factory)
    svg_io = io.BytesIO()
    qr_svg_img.save(svg_io)
    svg_bytes = svg_io.getvalue()
    qr_svg_url = upload_to_supabase(svg_bytes, f"qrcodes/qr_{pnr}.svg", "image/svg+xml")

    # --- NAYA: IMAGE SAVING LOGIC (SEEDHA CLOUD ME) ---
    photo_path = None
    aadhaar_path = None

    if 'photo' in request.files:
        photo_file = request.files['photo']
        if photo_file.filename != '':
            ext = photo_file.filename.split('.')[-1]
            p_filename = f"photos/photo_{pnr}.{ext}"
            # Seedha File read karke cloud me bhej do
            photo_path = upload_to_supabase(photo_file.read(), p_filename, photo_file.content_type)

    if 'aadhaar' in request.files:
        aadhaar_file = request.files['aadhaar']
        if aadhaar_file.filename != '':
            ext = aadhaar_file.filename.split('.')[-1]
            a_filename = f"aadhaar/aadhaar_{pnr}.{ext}"
            # Seedha File read karke cloud me bhej do
            aadhaar_path = upload_to_supabase(aadhaar_file.read(), a_filename, aadhaar_file.content_type)

    # --- SUPABASE DATA PREPARATION ---
    try:
        passenger_data = {
            "name": request.form.get('name'),
            "age": int(request.form.get('age')) if request.form.get('age') else 0,
            "blood_group": request.form.get('blood'),
            "group_name": request.form.get('group'), 
            "contact": request.form.get('contact'),
            "pnr": pnr,
            "medical": request.form.get('medical')
        }

        # Agar cloud upload successful raha, toh Database me URL save karo
        if qr_png_url:
            passenger_data["qr_path"] = qr_png_url
        if photo_path:
            passenger_data["photo_path"] = photo_path
        if aadhaar_path:
            passenger_data["aadhaar_path"] = aadhaar_path
        
        if p_id and p_id != 'null':
            # UPDATE EXISTING RECORD
            update_url = f"{SUPABASE_URL}/rest/v1/passengers?id=eq.{p_id}"
            response = requests.patch(update_url, headers=HEADERS, json=passenger_data)
            success_msg = f"{request.form.get('name')}'s profile updated successfully! ☁️"
        else:
            # CREATE NEW RECORD
            passenger_data["attendance_logs"] = {"General Boarding": "pending"}
            insert_url = f"{SUPABASE_URL}/rest/v1/passengers"
            response = requests.post(insert_url, headers=HEADERS, json=passenger_data)
            success_msg = f"{request.form.get('name')} safely saved to Cloud! ☁️"
        
        if response.status_code in [200, 201, 204]:
            return jsonify({
                "message": success_msg, 
                "qr_url": qr_png_url,     # Cloud link dega display ke liye
                "qr_svg_url": qr_svg_url  # Cloud link dega download ke liye
            })
        else:
            return jsonify({"error": "Failed to save to cloud"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. API - Cloud se sara data lene ke liye 
@app.route('/api/get_passengers', methods=['GET'])
def get_passengers():
    try:
        fetch_url = f"{SUPABASE_URL}/rest/v1/passengers?select=*&order=id.desc"
        response = requests.get(fetch_url, headers=HEADERS)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Failed to fetch from cloud"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================================================
# 🔥 SMART SOS ROUTE - QR SCAN HONE PAR YE CHALEGA 🔥
# =========================================================
@app.route('/p/<pnr>')
def passenger_profile(pnr):
    try:
        # 1. Passenger ki details nikalo
        fetch_url = f"{SUPABASE_URL}/rest/v1/passengers?pnr=eq.{pnr}&select=*"
        response = requests.get(fetch_url, headers=HEADERS)
        
        if response.status_code == 200 and len(response.json()) > 0:
            passenger = response.json()[0]
            group_name = passenger.get('group_name')
            
            # 2. Us passenger ke Group Admin ka number nikalo database se
            admin_phone = ""
            if group_name:
                contact_url = f"{SUPABASE_URL}/rest/v1/group_contacts?group_letter=eq.{group_name}&select=phone"
                contact_res = requests.get(contact_url, headers=HEADERS)
                if contact_res.status_code == 200 and len(contact_res.json()) > 0:
                    admin_phone = contact_res.json()[0].get('phone', '')

            # 3. HTML page ko dono cheezein bhej do (Passenger data + Admin Number)
            return render_template('sos.html', p=passenger, admin_phone=admin_phone)
        else:
            return "❌ YatraShield: PNR Not Found or Invalid QR Code", 404
            
    except Exception as e:
        return f"Error: {str(e)}", 500
# =========================================================


# 4. API - DYNAMIC JSON ATTENDANCE Update karne ke liye
@app.route('/api/update_status', methods=['POST'])
def update_status():
    data = request.json
    p_id = data.get('id')
    event_name = data.get('event_name') 
    new_status = data.get('status') 
    
    try:
        fetch_url = f"{SUPABASE_URL}/rest/v1/passengers?id=eq.{p_id}&select=attendance_logs"
        res = requests.get(fetch_url, headers=HEADERS)
        
        if res.status_code == 200 and len(res.json()) > 0:
            current_logs = res.json()[0].get('attendance_logs')
            if current_logs is None:
                current_logs = {}
            
            current_logs[event_name] = new_status 
            
            update_url = f"{SUPABASE_URL}/rest/v1/passengers?id=eq.{p_id}"
            patch_res = requests.patch(update_url, headers=HEADERS, json={"attendance_logs": current_logs})
            
            if patch_res.status_code in [200, 204]:
                return jsonify({"message": f"Status Updated for {event_name}!"})
            else:
                return jsonify({"error": "Failed to update cloud"}), 500
        else:
            return jsonify({"error": "Passenger not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 5. API - SAVE GROUP CONTACTS
@app.route('/api/save_group_contacts', methods=['POST'])
def save_group_contacts():
    contacts = request.json
    try:
        del_url = f"{SUPABASE_URL}/rest/v1/group_contacts?group_letter=not.is.null"
        requests.delete(del_url, headers=HEADERS)

        data_to_insert = [{"group_letter": k, "phone": v} for k, v in contacts.items() if str(v).strip()]
        
        if data_to_insert:
            insert_url = f"{SUPABASE_URL}/rest/v1/group_contacts"
            requests.post(insert_url, headers=HEADERS, json=data_to_insert)

        return jsonify({"message": "Contacts saved securely to Cloud!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 6. API - GET GROUP CONTACTS
@app.route('/api/get_group_contacts', methods=['GET'])
def get_group_contacts():
    try:
        fetch_url = f"{SUPABASE_URL}/rest/v1/group_contacts?select=*"
        res = requests.get(fetch_url, headers=HEADERS)
        if res.status_code == 200:
            contacts_dict = {item['group_letter']: item['phone'] for item in res.json()}
            return jsonify(contacts_dict)
        return jsonify({})
    except Exception as e:
        return jsonify({}), 500

# 7. API - NAYA DELETE PASSENGER
@app.route('/api/delete_passenger', methods=['POST'])
def delete_passenger():
    data = request.json
    p_id = data.get('id')
    try:
        del_url = f"{SUPABASE_URL}/rest/v1/passengers?id=eq.{p_id}"
        response = requests.delete(del_url, headers=HEADERS)
        if response.status_code in [200, 204]:
            return jsonify({"message": "Passenger deleted successfully"})
        else:
            return jsonify({"error": "Failed to delete"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# 🔥 NAYA ROUTE: ZABARDASTI DOWNLOAD KARWANE KE LIYE 🔥
@app.route('/download_qr/<file_type>/<pnr>')
def download_qr_proxy(file_type, pnr):
    try:
        ext = 'png' if file_type.lower() == 'png' else 'svg'
        content_type = 'image/png' if ext == 'png' else 'image/svg+xml'
        file_name = f"qr_{pnr}.{ext}"
        
        # Cloud se file fetch karna
        supabase_public_url = f"{SUPABASE_URL}/storage/v1/object/public/yatra_assets/qrcodes/{file_name}"
        response = requests.get(supabase_public_url)
        
        if response.status_code == 200:
            # As attachment bhejna (Taki new tab me na khule, direct download ho)
            return send_file(
                io.BytesIO(response.content),
                mimetype=content_type,
                as_attachment=True,
                download_name=f"YatraShield_QR_{pnr}.{ext}"
            )
        return "File not found", 404
    except Exception as e:
        return str(e), 500
if __name__ == '__main__':
    app.run(debug=True)