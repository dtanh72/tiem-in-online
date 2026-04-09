from flask import Blueprint, render_template
from flask_login import login_required

tools_bp = Blueprint('tools', __name__, url_prefix='/tools')

@tools_bp.route('/calculators')
@login_required
def calculators_page():
    # Pass a default tools page entirely handled by JS.
    return render_template('tools/calculators.html')
