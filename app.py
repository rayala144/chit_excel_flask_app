from flask import Flask, render_template, request, send_file
from io import BytesIO
from openpyxl import load_workbook
from mod_excel import *


app = Flask(__name__)

# app.config['TEMPLATES_AUTO_RELOAD'] = True
# app.config['TEMPLATE_FOLDER'] = os.path.abspath('templates')

@app.route('/', methods=['GET', 'POST'])

def upload_file():
    if request.method == 'POST':

        if 'file' not in request.files:
            return "File not uploaded yet"
        
        file = request.files['file']

        if file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):

            my_workbook = load_workbook(filename=BytesIO(file.read()))
            updated_workbook = update_excel(my_workbook)

            # output_file = add_suffix_to_filename(file, '_updated')
            output = BytesIO()
            updated_workbook.save(output)
            output.seek(0)

            output_file = add_suffix_to_filename(file.filename, '_updated')

            # Return the updated file for download
            return send_file(output, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', download_name=output_file)
        
        else:
            return 'Invalid file format. Only Excel files are allowed'
        
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
