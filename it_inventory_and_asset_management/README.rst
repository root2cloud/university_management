================================================================
IT Asset Management
================================================================

The **IT Asset Management** module allows organizations to efficiently track and manage their IT infrastructure. It provides a structured way to manage **Systems**, **Assets**, and **Components**, where each entity is linked to the other, enabling complete visibility of your IT resources. Assets can be assigned to users, and an interactive dashboard gives a quick overview of the data.

role:: raw-html(raw)
:format: html

**Table of contents**

.. contents::
   :local:


Features
================================================================

- Manage **Systems**, **Assets**, and **Components** with clear relationships.
- Link multiple Assets to a single System.
- Link multiple Components to a single Asset.
- Assign Systems, Assets, and Components to specific users.
- Dashboard view for quick insights and status summaries.
- Search, filter, and sort functionality for quick data access.


Relationships
================================================================

- **System → Asset**: Each System can have multiple linked Assets.
- **Asset → Component**: Each Asset can have multiple linked Components.
- **User Assignment**: Systems, Assets, and Components can be assigned to users for accountability and tracking.


Installation
================================================================

**To install this, follow below steps:**

* Place this module in your Odoo's custom addons directory.
* Install the module from **Main Apps** section in Odoo.


**How to use this module:**

1. After installation add the user to the group **IT Asset User**.
   .. image:: it_asset_management/static/description/assets/Figma/it_asset_management_group_updated.png
      :alt: Components List
      :width: 300px

2. Navigate to the **IT Asset Management** menu in Odoo.

3. Create a **Component** record.

   .. image:: it_asset_management/static/description/assets/Figma/component_create.png
      :alt: Components List
      :width: 300px

4. Add **Assets** and link them to the relevant Components.

   .. image:: it_asset_management/static/description/assets/Figma/asset_create.png
      :alt: Assets List
      :width: 300px

5. Add **Systems** and link them to the relevant Assets.

   .. image:: it_asset_management/static/description/assets/Figma/system_create.png
      :alt: Systems List
      :width: 300px

6. Assign the System, Asset, or Component to a user.

7. View the **Dashboard** for overall statistics, such as:
   - Total Systems, Assets, and Components.
   - Assignments by user.
   - Status breakdown (Active, In Maintenance, Retired).

   .. image:: it_asset_management/static/description/assets/Figma/it_asset_dashboard.png
      :alt: IT Asset Dashboard
      :width: 300px



Change logs
================================================================

17.0.1.0.0
*****************
* ``Added`` IT Asset Management module with Systems, Assets, Components, User Assignments, and Dashboard.


License
================================================================

This module is licensed under the OPL-1 License.


Support
================================================================

`Techinfini Solutions Pvt Ltd <https://techinfini.in/>`_
