from warehouse.runner import WarehouseRunner
from warehouse.models import ReportRun
from logistics.models import SupplyPoint, ProductReport
from logistics.util import config
from logistics_project.apps.malawi.util import group_for_location, hsas_below,\
    hsa_supply_points_below
from logistics.const import Reports
from dimagi.utils.dates import months_between, first_of_next_month
from datetime import datetime, timedelta
from logistics_project.apps.malawi.warehouse_models import ReportingRate
from django.conf import settings
from django.db.models import Sum

class MalawiWarehouseRunner(WarehouseRunner):
    """
    Malawi's implementation of the warehouse runner. 
    """
    skip_hsas = False
    skip_aggregates = False
    
    def cleanup(self, start, end):
        print "Malawi warehouse cleanup!"  
        # TODO: fix this up - currently deletes all records having any data
        # within the period
        ReportRun.objects.filter(start__gte=start, end__lte=end).delete()
        ReportingRate.objects.filter(date__gte=start, date__lte=end).delete()
    
    def generate(self, start, end):
        print "Malawi warehouse generate!"
        # first populate all the warehouse tables for all facilities
        hsas = SupplyPoint.objects.filter(active=True, type__code='hsa').order_by('id')
        if not self.skip_hsas:
            for hsa in hsas:
                # process all the hsa-level warehouse tables
                is_em_group = (group_for_location(hsa.location) == config.Groups.EM)
                products_managed = set([c.pk for c in hsa.commodities_stocked()])
                        
                print "processing hsa %s (%s) is em: %s" % (hsa.name, str(hsa.id), is_em_group)
                
                for year, month in months_between(start, end):
                    window_date = datetime(year, month, 1)
                    next_window_date = first_of_next_month(window_date)
                    period_start = max(window_date, start)
                    period_end = min(next_window_date, end)
                    late_cutoff = window_date + timedelta(days=settings.LOGISTICS_DAYS_UNTIL_LATE_PRODUCT_REPORT)
                    
                    # process reports (on time versus late, versus at all and completeness)
                    reports_in_range = ProductReport.objects.filter\
                        (supply_point=hsa, report_type__code=Reports.SOH,
                         report_date__gte=period_start, report_date__lte=period_end)
                    period_rr = ReportingRate.objects.get_or_create\
                        (supply_point=hsa, date=window_date)[0]
                    period_rr.total = 1
                    period_rr.reported = 1 if reports_in_range else period_rr.reported
                    # for the em group "on time" is meaningful, for the ept group 
                    # they are always considered "on time" 
                    if reports_in_range and is_em_group:
                        first_report_date = reports_in_range.order_by('report_date')[0].report_date
                        period_rr.on_time = first_report_date <= late_cutoff or period_rr.on_time
                    else:
                        period_rr.on_time = period_rr.on_time if is_em_group else period_rr.reported
                    
                    if not period_rr.complete:
                        # check for completeness (only if not already deemed complete)
                        # unfortunately, we have to walk all avaialable 
                        # transactions in the period every month 
                        # in order to do this correctly.
                        this_months_reports = ProductReport.objects.filter\
                            (supply_point=hsa, report_type__code=Reports.SOH,
                             report_date__gte=window_date, report_date__lte=period_end)
                        
                        found = set(this_months_reports.values_list("product", flat=True).distinct())
                        period_rr.complete = 0 if found and (products_managed - found) else \
                            (1 if found else 0)
                        
                    period_rr.save()
                    
        # rollup aggregates
        non_hsas = SupplyPoint.objects.filter(active=True)\
            .exclude(type__code='hsa').order_by('id')
        for place in non_hsas:
            print "processing non-hsa %s (%s)" % (place.name, str(place.id))
            relevant_hsas = hsa_supply_points_below(place.location)
            
            for year, month in months_between(start, end):
                window_date = datetime(year, month, 1)
                _aggregate(ReportingRate, window_date, place, relevant_hsas, 
                           fields=['total', 'reported', 'on_time', 'complete'])
                
def _aggregate(modelclass, window_date, supply_point, base_supply_points, fields):
    """
    Aggregate an instance of modelclass, by summing up all of the fields for
    any matching models found in the same date range in the base_supply_points.
    
    Returns the updated reporting model class.
    """
    period_instance = modelclass.objects.get_or_create\
        (supply_point=supply_point, date=window_date)[0]
    children_qs = modelclass.objects.filter\
        (date=window_date, supply_point__in=base_supply_points)
    totals = children_qs.aggregate(*[Sum(f) for f in fields])
    [setattr(period_instance, f, totals["%s__sum" % f] or 0) for f in fields]
    period_instance.save()
    return period_instance