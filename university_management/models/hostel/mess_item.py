# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MessItem(models.Model):
    _name = 'mess.item'
    _description = 'Mess Food Items'
    _order = 'name'

    name = fields.Char(string='Item Name', required=True)

    # Category
    category = fields.Selection([
        ('main_course', 'Main Course'),
        ('side_dish', 'Side Dish'),
        ('bread', 'Bread/Roti'),
        ('rice', 'Rice'),
        ('dal', 'Dal/Sambar'),
        ('vegetable', 'Vegetable'),
        ('salad', 'Salad'),
        ('dessert', 'Dessert'),
        ('beverage', 'Beverage'),
        ('fruit', 'Fruit'),
    ], string='Category', required=True)

    # Type
    item_type = fields.Selection([
        ('veg', 'Vegetarian'),
        ('non_veg', 'Non-Vegetarian'),
        ('vegan', 'Vegan'),
        ('jain', 'Jain'),
    ], string='Type', default='veg')

    # Nutrition (optional)
    calories = fields.Float(string='Calories')

    # Description
    description = fields.Text(string='Description')

    active = fields.Boolean(string='Active', default=True)
