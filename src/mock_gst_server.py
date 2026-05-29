from flask import Flask, request, jsonify
from datetime import datetime
import json
import csv
import os

app = Flask(__name__)

# Helper to load JSON
def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

# Helper to load CSV
def load_csv(path):
    data = []
    if os.path.exists(path):
        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
    return data

# Load mock data
BASE_DATA_PATH = 'data/master_data'
vendors_data = load_json(f'{BASE_DATA_PATH}/vendor_registry.json').get('vendors', [])
vendors = {v['gstin']: v for v in vendors_data if v.get('gstin')}
hsn_codes = load_json(f'{BASE_DATA_PATH}/hsn_sac_codes.json')
gst_rates = load_csv(f'{BASE_DATA_PATH}/gst_rates_schedule.csv')

@app.route('/api/gst/validate-gstin', methods=['POST'])
def validate_gstin():
    data = request.json
    gstin = data.get('gstin', '').upper().strip()
    
    if len(gstin) != 15 or not gstin.isalnum():
        return jsonify({
            'valid': False,
            'error': 'INVALID_FORMAT',
            'message': 'GSTIN must be 15 characters alphanumeric'
        }), 400
    
    vendor = vendors.get(gstin)
    if not vendor:
        return jsonify({
            'valid': False,
            'error': 'NOT_FOUND',
            'message': 'GSTIN not registered in GST system'
        }), 404
    
    response = {
        'valid': True,
        'gstin': gstin,
        'legal_name': vendor['legal_name'],
        'trade_name': vendor.get('trade_name'),
        'status': vendor['status'],
        'state_code': vendor['state_code'],
        'state': vendor['state'],
        'taxpayer_type': vendor.get('gst_filing_status', 'Regular'),
        'registration_date': vendor.get('registration_date')
    }
    
    if vendor['status'] == 'SUSPENDED':
        response['suspension_date'] = vendor.get('suspension_date')
        response['suspension_reason'] = vendor.get('suspension_reason')
    
    return jsonify(response)

@app.route('/api/gst/validate-irn', methods=['POST'])
def validate_irn():
    data = request.json
    irn = data.get('irn', '')
    
    # Mock behavior: IRNs starting with 'invalid' are invalid
    if irn.startswith('invalid'):
        return jsonify({
            'valid': False,
            'error': 'IRN_NOT_FOUND',
            'message': 'IRN does not exist in e-Invoice system'
        }), 404
    
    # Mock success response
    return jsonify({
        'valid': True,
        'irn': irn,
        'status': 'ACTIVE',
        'generation_date': datetime.now().isoformat(),
        'invoice_details': {
            'seller_gstin': '27AABCT1234F1ZP',
            'buyer_gstin': '27AABCF9999K1ZX',
            'invoice_number': 'TS/MH/2024/001234',
            'invoice_date': '2024-09-15',
            'invoice_value': 590000
        }
    })

@app.route('/api/gst/hsn-rate', methods=['GET'])
def get_hsn_rate():
    code = request.args.get('code')
    date_str = request.args.get('date')
    
    if not code or not date_str:
        return jsonify({'error': 'MISSING_PARAMS', 'message': 'Code and date are required'}), 400
    
    try:
        req_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'INVALID_DATE', 'message': 'Date must be YYYY-MM-DD'}), 400

    # Find applicable rate
    applicable_rate = None
    for rate in gst_rates:
        if rate['hsn_sac_code'] == code:
            eff_from = datetime.strptime(rate['effective_from'], '%Y-%m-%d')
            eff_to = rate['effective_to']
            eff_to_date = datetime.strptime(eff_to, '%Y-%m-%d') if eff_to else datetime.max
            
            if eff_from <= req_date <= eff_to_date:
                applicable_rate = rate
                break
    
    if not applicable_rate:
        # Fallback to default rate if code not found
        applicable_rate = next((r for r in gst_rates if r['hsn_sac_code'] == '99'), None)

    if applicable_rate:
        return jsonify({
            'hsn_sac': code,
            'description': applicable_rate['description'],
            'applicable_date': date_str,
            'rate': {
                'cgst': float(applicable_rate['rate_cgst']),
                'sgst': float(applicable_rate['rate_sgst']),
                'igst': float(applicable_rate['rate_igst'])
            },
            'effective_from': applicable_rate['effective_from'],
            'effective_to': applicable_rate.get('effective_to'),
            'notes': applicable_rate.get('special_conditions', '')
        })

    return jsonify({'error': 'RATE_NOT_FOUND', 'message': 'No rate found for given HSN and date'}), 404

@app.route('/api/gst/e-invoice-required', methods=['POST'])
def e_invoice_required():
    data = request.json
    seller_gstin = data.get('seller_gstin')
    invoice_value = data.get('invoice_value', 0)
    
    vendor = vendors.get(seller_gstin)
    if not vendor:
        return jsonify({'required': False, 'reason': 'Vendor not found'})

    turnover = vendor.get('turnover_last_fy', 0)
    threshold = 50000000 # 5 Cr threshold
    
    required = turnover > threshold
    return jsonify({
        'required': required,
        'reason': 'Seller turnover exceeds threshold' if required else 'Turnover below threshold',
        'seller_turnover_fy_prev': turnover,
        'threshold': threshold,
        'mandate_date': '2022-10-01'
    })

@app.route('/api/gst/verify-206ab', methods=['POST'])
def verify_206ab():
    data = request.json
    pan = data.get('pan', '').upper()
    
    # Check in vendors
    applicable = False
    reason = "Filer of ITR"
    
    for v in vendors.values():
        if v.get('pan') == pan and v.get('section_206ab_applicable'):
            applicable = True
            reason = "Non-filer of ITR for previous years"
            break
            
    return jsonify({
        'pan': pan,
        'section_206ab_applicable': applicable,
        'reason': reason,
        'verification_date': datetime.now().strftime('%Y-%m-%d')
    })

if __name__ == '__main__':
    print("Starting Mock GST Server on port 8080...")
    app.run(port=8080, debug=False, use_reloader=False)
