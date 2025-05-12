# -*- coding: utf-8 -*-
# from odoo import http


# class GplFleet(http.Controller):
#     @http.route('/gpl_fleet/gpl_fleet', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/gpl_fleet/gpl_fleet/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('gpl_fleet.listing', {
#             'root': '/gpl_fleet/gpl_fleet',
#             'objects': http.request.env['gpl_fleet.gpl_fleet'].search([]),
#         })

#     @http.route('/gpl_fleet/gpl_fleet/objects/<model("gpl_fleet.gpl_fleet"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('gpl_fleet.object', {
#             'object': obj
#         })

