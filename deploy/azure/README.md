# Deploying AdventureHive on an Azure VM (Azure for Students)

Result: `https://<your-name>.<region>.cloudapp.azure.com/ps4/` with HTTPS, the PS4 research pages,
the clickable prototype (`/ps4/prototype/`), the API and `/admin/`.

## 1. Create the VM (Azure portal, about 10 min)
1. portal.azure.com → **Virtual machines** → **Create** → **Azure virtual machine**.
2. Subscription **Azure for Students** · Resource group **Create new: adventurehive-rg** · Name **adventurehive**.
3. Region **(Asia Pacific) Southeast Asia** · Image **Ubuntu Server 24.04 LTS** · Size **Standard_B1ms**
   (if it is not offered, pick another small B-series size that is).
4. Authentication **Password** · Username **azureuser** · a strong password you keep safe.
5. Public inbound ports: allow **SSH (22)**, **HTTP (80)**, **HTTPS (443)**.
6. **Review + create** → **Create**, then **Go to resource**.
7. Overview → **DNS name: Not configured** → set a label such as `adventurehive-tlc` → **Save**.
   Your address is shown as e.g. `adventurehive-tlc.southeastasia.cloudapp.azure.com`.

## 2. Upload the code (from your Windows PowerShell, in the project folder)
Commit first, then:
```powershell
git archive -o adventurehive.zip HEAD
scp adventurehive.zip azureuser@<DNS-NAME>:~
ssh azureuser@<DNS-NAME>
```
`git archive` packs only committed files: no `.env`, no `media/`, no `node_modules`.

## 3. Install everything (on the VM)
```bash
sudo apt-get update && sudo apt-get install -y unzip
unzip -o adventurehive.zip -d adventurehive
cd adventurehive
bash deploy/azure/setup.sh <DNS-NAME>
.venv/bin/python manage.py createsuperuser
```
`setup.sh` installs PostgreSQL, Nginx and Gunicorn, writes a production `.env` (only if none exists),
creates the tables, loads the demo data and gets a free HTTPS certificate.

## 4. Updating later
On Windows: commit, `git archive -o adventurehive.zip HEAD`, `scp adventurehive.zip azureuser@<DNS-NAME>:~`. Then on the VM:
```bash
cd ~ && unzip -o adventurehive.zip -d adventurehive && cd adventurehive && bash deploy/azure/update.sh
```
`update.sh` never touches `.env` or the data.

## Useful commands (on the VM)
| What | Command |
|---|---|
| App log | `sudo journalctl -u adventurehive -n 50` |
| Restart app | `sudo systemctl restart adventurehive` |
| Nginx errors | `sudo tail -n 30 /var/log/nginx/error.log` |
| Reset demo posts | `.venv/bin/python manage.py seed_demo_posts --reset` |

Stop or delete the VM in the portal when grading is over, so it stops using credit.
