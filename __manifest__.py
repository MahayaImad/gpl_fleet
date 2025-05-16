# -*- coding: utf-8 -*-
{
    'name': "GPL Installation",

    'summary': "Gestion des installations GPL",

    'description': """
        Gestion des installations GPL sur véhicules
        avec gestion des kits comme articles.
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'fleet',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': [
            'base',
            'fleet',  # For fleet.vehicle.model references
            'product',  # For product.product and product.template
            'stock',  # For stock.picking
            'mrp',  # For mrp.bom references
            'hr',  # For hr.employee (technician_id)
            'purchase',
            'account',  # For account.move (invoice_id)
            'mail',# For mail.thread, mail.activity.mixin
            'sale',
        ],
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/gpl_security.xml',
        'data/ir_sequence_data.xml',

        'views/fleet_vehicle_model_views.xml',
        'views/gpl_vehicle_views.xml',
        'views/gpl_installation_views.xml',
        'views/gpl_repair_views.xml',
        'views/gpl_inspection_views.xml',
        'views/gpl_reservoir_testing_views.xml',

        'views/product_template.xml',
        'views/res_config_settings_views.xml',
        'views/gpl_menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
