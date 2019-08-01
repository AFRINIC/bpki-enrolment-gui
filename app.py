from __future__ import absolute_import
import os
import logging
from pathlib import Path
from flask import Flask, request, render_template, abort, send_file, send_from_directory
import OpenSSL.crypto as crypt
from csr import CsrGenerator
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import *
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
import hashlib
import binascii

app = Flask(__name__)
base_directory = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(filename=base_directory + '/logs/enrolment.log', format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)
# app.config['P12_PATH'] = base_directory + '/p12'
user_errors = []
server_errors = []


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')


@app.route('/security')
def security():
    return render_template('security.html')


@app.route('/generate', methods=['POST'])
def generate_csr():
    nic_id = request.form['CN']

    csr = CsrGenerator(request.form)
    # response = b'\n'.join([csr.csr, csr.private_key])
    # nic_id = request.form['CN']
    password = request.form['password']
    org_id = request.form['org_id']
    user_directory = generate_hash(nic_id, org_id)[:12]
    generate_pem(nic_id, user_directory, password, csr.csr)
    generate_p12(nic_id, user_directory, password, csr.private_key)

    file_url = '/certificate' + base_directory + '/downloads/' + user_directory + '/' + nic_id + '.p12'
    return render_template('success.html', url=file_url)

    # if user_errors:
    #     return redirect('/user-error')
    #
    # elif server_errors:
    #     return redirect('/server-error')
    #
    # return redirect('/certificate' + nic_id + '.pem')
    # return Response(response, mimetype='text/plain')


def generate_pem(nic_id, user_directory, password, csr):
    downloads = base_directory + '/downloads/' + user_directory

    try:
        os.mkdir(downloads)

    except FileExistsError:
        pass

    except OSError as error:
        print(error)
        server_errors.append(error)
        logger.error('Unable to create path: %s -- %s', error, nic_id)

    # for file in os.listdir(downloads):
    #     file_name = os.path.join(downloads, file)
    #     try:
    #         if os.path.isfile(file_name):
    #             os.unlink(file_name)
    #     except OSError as error:
    #         print('Unable to delete file:', error)
    #         logger.error('Unable to delete file: %s --NIC Handle: %s', error, nic_id)

    opts = webdriver.ChromeOptions()
    opts.add_argument('--no-sandbox')
    # opts.add_argument('--headless')
    opts.add_argument('--disable-dev-shm-usage')
    log_path = base_directory + '/logs/chromedriver.log'
    prefs = {'download.default_directory': downloads}
    # prefs = {'download.default_directory': base_directory + '/downloads'}
    opts.add_experimental_option("prefs", prefs)

    browser = webdriver.Chrome(base_directory + '/chromedriver', options=opts,
                               service_args=['--verbose', '--log-directory=' + log_path])
    browser.get('https://externalra.afrinic.net/externalra-gui/facelet/enroll-csrcert.xhtml')

    pem_checkbox = browser.find_element_by_id('form:j_id71:_1')
    pem_checkbox.click()
    username = browser.find_element_by_id('form:username')
    username.send_keys(nic_id)

    form_password = browser.find_element_by_id('form:secretPassword')
    form_password.send_keys(password)

    certificate_form = browser.find_element_by_id('form:certificateRequest')
    certificate_form.send_keys((Keys.CONTROL + "a"), Keys.DELETE)
    certificate_form.send_keys(csr.decode('utf-8'))

    submit = browser.find_element_by_id('form:j_id77')
    submit.click()

    try:
        load_complete = WebDriverWait(browser, 30).until(expected_conditions.presence_of_element_located((By.CLASS_NAME,
                                                                                    'iceOutConStatInactv')))
    except TimeoutError as error:
        server_errors.append(error)
        logger.error('Unable to receive pem file: %s -- NIC Handle: %s', error, nic_id)
        browser.close()
        browser.quit()
        abort(500)

    # downloaded_pem_path = Path(base_directory + '/downloads/' + user_directory + '/' + nic_id + '.pem')
    downloaded_pem_path = Path(downloads + '/' + nic_id + '.pem')

    if downloaded_pem_path.exists() and downloaded_pem_path.is_file():
        browser.close()
        browser.quit()

    else:
        try:
            element = WebDriverWait(browser, 30).until(expected_conditions.presence_of_element_located(
                (By.CLASS_NAME, 'iceMsgsError')))
            error_msg = element.text
            browser.implicitly_wait(3)
            browser.close()
            browser.quit()

            if error_msg not in user_errors:
                user_errors.append(error_msg)
            print(user_errors)

        except TimeoutException as error:
            print(error)
            logger.error('Unable to retrieve error. Operation timeout: %s --NIC Handle: %s', error, nic_id)
            server_errors.append(error)

        except NoSuchElementException as error:
            print(error)
            logger.error('Unable to retrieve error message: %s --NIC Handle: %s', error, nic_id)
            server_errors.append(error)

    if user_errors:
        abort(412)

    if server_errors:
        abort(500)


def generate_p12(nic_id, user_directory, password, private_key):
    download_path = base_directory + '/downloads/' + user_directory
    pem_file = download_path + '/' + nic_id + '.pem'
    output = download_path + '/' + nic_id + '.p12'

    try:
        with open(pem_file, 'rb') as pem_file:
            pem_buffer = pem_file.read()
            pem = crypt.load_certificate(crypt.FILETYPE_PEM, pem_buffer)

    except IOError as error:
        print('Could not read pem file. Make sure file exists and you have the right permission. ', error)
        logger.error('Could not read pem file. Make sure file exists and you have the right permission: %s '
                     '-- NIC Handle: %s', error, nic_id)
        server_errors.append(error)
        abort(500)

    try:
        private_key = crypt.load_privatekey(crypt.FILETYPE_PEM, private_key)
        pfx = crypt.PKCS12Type()
        pfx.set_privatekey(private_key)

        try:
            pfx.set_certificate(pem)
            pfx_data = pfx.export(password)

        except crypt.Error as error:
            print('An unexpected error occurred', error)
            logger.error('An unexpected error occurred: %s -- NIC Handle: %s', error, nic_id)
            server_errors.append(error)
            abort(500)

        try:
            with open(output, 'wb') as p12_file:
                p12_file.write(pfx_data)

        except IOError as error:
            print('Unable to write p12 file ', error)
            logger.error('Unable to write p12 file: %s --NIC Handle: %s', error, nic_id)
            server_errors.append(error)
            abort(500)

    except UnboundLocalError as error:
        print('Pem file not created:', error)
        logger.error('Pem file not created: %s --NIC Handle: %s', error, nic_id)
        server_errors.append(error)
        abort(500)

    except crypt.Error as error:
        print('An unexpected error occurred while generating p12 file:', error)
        logger.error('An unexpected error occurred while generating p12 file: %s --NIC Handle: %s', error, nic_id)
        server_errors.append(error)
        abort(500)


@app.route('/certificate/<path:file_path>')
def get_certificate(file_path):
    try:
        path_arr = file_path.split('/')
        file_name = path_arr[-1]
        file_directory = '/' + '/'.join(path_arr[:len(path_arr)-1])
        return send_from_directory(file_directory, filename=file_name, as_attachment=True)

    except FileNotFoundError:
        abort(404)


def generate_hash(nic_id, org_id):
    """Generate base_directory name from hash of nic handle and org handle"""
    nic_org = nic_id + org_id
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    dir_hash = hashlib.pbkdf2_hmac('sha512', nic_org.encode('utf-8'), salt, 100000)
    dir_hash = binascii.hexlify(dir_hash)
    return (salt + dir_hash).decode('ascii')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('server_error.html'), 500


@app.errorhandler(412)
def user_error(e):
    # return render_template('user_error.html'), 412
    return render_template('user_error.html', user_errors=user_errors)


@app.errorhandler(405)
def method_not_allowed(e):
    return render_template('405.html')


if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 5555))
    app.run(host='0.0.0.0', port=port, debug=True)
