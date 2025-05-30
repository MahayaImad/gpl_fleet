# === CONFIGURATION ET PARAMÈTRES ===
from . import res_config_settings

# === MODÈLES DE BASE ===
from . import res_partner
from . import product_template
from . import stock_lot
from . import mrp_bom

# === FABRICANTS ET RÉFÉRENCES ===
from . import gpl_reservoir_fabriquant

# === VÉHICULES ET SUIVI ===
from . import gpl_vehicle
from . import gpl_vehicle_tag
from . import gpl_vehicle_odometer

# === SERVICES ET OPÉRATIONS ===
from . import gpl_service
from . import gpl_repair
from . import gpl_inspection
from . import gpl_reservoir_testing

# === ASSISTANTS ET WIZARDS ===
from . import gpl_existing_installation_wizard

# === DASHBOARDS ET ANALYSES ===
from . import gpl_reservoir_dashboard

# === CONFIGURATION INITIALE ===
from . import gpl_setup_wizard
