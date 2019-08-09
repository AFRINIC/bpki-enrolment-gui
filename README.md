# BPKI Enrolment Helper
The aim of this tool is to provide a GUI to user to (1) generate a CSR and private key (2) automatically sends the CSR  the AFRINIC BPKI RA to retrieve the CERTIFICATE.

It's a pretty simple Flask webapp which generates a Certificate Signing Request for creating SSL certificates. Of course, if you are smart, you can run the same thing on command-line.

## Installation Guide
### For Development
1. Ensure you have python 3  and pip3 installed.  
2. Clone project.
3. Create a virtual environment for the project.
4. Run ```pip3 install -r requirements.txt``` in your virtual environment to install requirements
5. Use ```python3 firefox_bpki.py``` to run the version that uses firefox driver or ```python3 chrome_bpki.py``` to run the version that uses chrome driver.

**Note:** You need to have chrome or firefox browser installed before you can use its driver. 
Following the above instructions will start Flask's inbuilt server which is for development only.

### For Production
**Note:** This tutorial uses **apt** as package manager so kindly use the appropriate package manager of the linux distribution the deployment is happening on.
Only one browser is used at a time and hence, you can choose to install either Chrome or Firefox. However you need to run the appropriate file for the browser.
1. Download and install Chrome manually or install Firefox using ```sudo apt install firefox```
2. Install Python 3 and related packages if not already installed using ```sudo apt install python3 python3-venv python3-dev```
3. Install nginx server using ```sudo apt install nginx```
4. Clone project into the directory you want to deploy to. 
5. Create a virtual Python environment and activate it.
6. In the activated Python environment, run ```pip3 install -r requirements.txt```
7. The production server used is Green Unicorn(gunicorn) and the documentation for server configuration can be found  [here](http://docs.gunicorn.org/en/stable/deploy.html). Use it to complete the server configuration as required.
8. Configure supervisor to restart app when it crashes. You can also use any other application as deemed fit to achieve the same purpose to ensure that the application is always running.
9. Configure Nginx server as required. 
10. Start the required services thus, Nginx and the gunicorn server.

