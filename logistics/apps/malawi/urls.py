#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.conf.urls.defaults import *

urlpatterns = patterns('',

    url(r'^dashboard/$',
        "logistics.apps.malawi.views.dashboard",
        name="malawi_dashboard"),
    url(r'^places/$',
        "logistics.apps.malawi.views.places",
        name="malawi_places"),
    url(r'^contacts/$',
        "logistics.apps.malawi.views.contacts",
        name="malawi_contacts"),
    url(r'^hsas/$',
        "logistics.apps.malawi.views.hsas",
        name="malawi_hsas"),
    url(r'^hsa/(?P<code>\d+)/$',
        "logistics.apps.malawi.views.hsa",
        name="malawi_hsa"),
    url(r'^help/$',
        "logistics.apps.malawi.views.help",
        name="malawi_help"),
    url(r'^status/$',
        "logistics.apps.malawi.views.status",
        name="malawi_status"),
    url(r'^airtel-users/$',
        "logistics.apps.malawi.views.airtel_numbers",
        name="malawi_airtel"),
    url(r'^scmgr/receiver/$',
        "logistics.apps.malawi.views.scmgr_receiver",
        name="malawi_scmgr_receiver"),
    url(r'^facilities/$',
        "logistics.apps.malawi.views.facilities",
        name="malawi_facilities"),
    url(r'^facilities/(?P<code>\d+)/$',
        "logistics.apps.malawi.views.facility",
        name="malawi_facility"),
    url(r'^products/$',
        "logistics.apps.malawi.views.products",
        name="malawi_products"),
    url(r'^monitoring/$',
        "logistics.apps.malawi.views.monitoring",
        name="malawi_monitoring"),
    url("^monitoring/(?P<report_slug>[\w_]+)/$", 
        "logistics.apps.malawi.views.monitoring_report",
        name="malawi_monitoring_report")
) 



