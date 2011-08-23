from datetime import datetime
from logistics.reports import Colors, PieChartData
from logistics.models import SupplyPoint
from models import DeliveryGroups, SupplyPointStatusTypes, SupplyPointStatusValues
from django.utils.translation import ugettext as _
from utils import sps_with_latest_status
from calendar import month_name

class SupplyPointStatusBreakdown(object):

    def __init__(self, facilities=None, report_date=None):
        if not report_date: report_date = datetime.utcnow()
        self.report_date = report_date
        if not facilities:
            facilities = SupplyPoint.objects.filter(type__code="facility")

        year = report_date.year
        month = report_date.month


        self.submitted = list(sps_with_latest_status(sps=facilities,
                                                year=year, month=month,
                                                status_type=SupplyPointStatusTypes.R_AND_R_FACILITY,
                                                status_value=SupplyPointStatusValues.SUBMITTED))

        self.not_submitted = list(sps_with_latest_status(sps=facilities,
                                                 year=year, month=month,
                                                 status_type=SupplyPointStatusTypes.R_AND_R_FACILITY,
                                                 status_value=SupplyPointStatusValues.NOT_SUBMITTED))

        self.not_responding = list(sps_with_latest_status(sps=facilities,
                                                 year=year, month=month,
                                                 status_type=SupplyPointStatusTypes.R_AND_R_FACILITY,
                                                 status_value=SupplyPointStatusValues.REMINDER_SENT))

        self.delivery_received = list(sps_with_latest_status(sps=facilities,
                                                 year=year, month=month,
                                                 status_type=SupplyPointStatusTypes.DELIVERY_FACILITY,
                                                 status_value=SupplyPointStatusValues.RECEIVED)) + \
                                 list(sps_with_latest_status(sps=facilities,
                                                 year=year, month=month,
                                                 status_type=SupplyPointStatusTypes.DELIVERY_FACILITY,
                                                 status_value=SupplyPointStatusValues.QUANTITIES_REPORTED))

        self._submission_chart = None

    def submission_chart(self):
        graph_data = [
                {"display": _("Submitted"),
                 "value": len(self.submitted),
                 "color": Colors.GREEN,
                 "description": "(%s) Submitted (%s)" % \
                    (len(self.submitted), self.report_date)
                },
                {"display": _("Haven't Submitted"),
                 "value": len(self.not_submitted),
                 "color": Colors.RED,
                 "description": "(%s) Haven't Submitted (%s)" % \
                    (len(self.not_submitted), self.report_date)
                },
                {"display": _("Didn't Respond"),
                 "value": len(self.not_responding),
                 "color": Colors.PURPLE,
                 "description": "(%s) Didn't Respond (%s)" % \
                    (len(self.not_responding), self.report_date)
                }
            ]
        self._submission_chart = PieChartData("Submission Status (%s %s)" % (month_name[self.report_date.month], self.report_date.year), graph_data)
        return self._submission_chart