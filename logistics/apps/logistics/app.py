#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

"""
The main purpose of this app is to parse reports of stock on hand and receipts
Look at the unit tests for specific examples.
"""

import re
from rapidsms.conf import settings
from django.utils.translation import ugettext as _
from rapidsms.apps.base import AppBase
from rapidsms.contrib.scheduler.models import EventSchedule, \
    set_weekly_event, set_monthly_event
from logistics.apps.logistics.models import Product, ProductReportsHelper, \
    STOCK_ON_HAND_REPORT_TYPE, GET_HELP_MESSAGE
from logistics.apps.logistics.errors import UnknownCommodityCodeError
from logistics.apps.logistics.models import REGISTER_MESSAGE

ERR_MSG = _("Please send your stock on hand in the format 'soh <product> <amount> <product> <amount>'")
NO_SUPPLY_POINT_MESSAGE = "You are not associated with a facility. Please contact your district administrator for assistance."
SOH_HELP_MESSAGE = "To report stock on hand, send SOH [space] [product code] [space] [amount]"
SOH_KEYWORD = 'soh'

class App(AppBase):
    bootstrapped = False

    def start (self):
        """Configure your app in the start phase."""
        if not self.bootstrapped:
            self.bootstrapped = True
            
            # set up first soh reminder
            try:
                EventSchedule.objects.get(callback="logistics.apps.logistics.schedule.first_soh_reminder")
            except EventSchedule.DoesNotExist:
                # 2:15 pm on Thursdays
                set_weekly_event("logistics.apps.logistics.schedule.first_soh_reminder",3,13,58)

            # set up second soh reminder
            try:
                EventSchedule.objects.get(callback="logistics.apps.logistics.schedule.second_soh_reminder")
            except EventSchedule.DoesNotExist:
                # 2:15 pm on Mondays
                set_weekly_event("logistics.apps.logistics.schedule.second_soh_reminder",0,13,57)

            # set up third soh reminder
            try:
                EventSchedule.objects.get(callback="logistics.apps.logistics.schedule.third_soh_to_super")
            except EventSchedule.DoesNotExist:
                # 2:15 pm on Wednesdays
                set_weekly_event("logistics.apps.logistics.schedule.third_soh_to_super",2,13,54)
                #schedule = EventSchedule(callback="logistics.apps.logistics.schedule.third_soh_to_super", 
                #                         hours='*', minutes='*', callback_args=None )
                #schedule.save()

            # set up rrirv reminder
            try:
                EventSchedule.objects.get(callback="logistics.apps.logistics.schedule.reminder_to_submit_RRIRV")
            except EventSchedule.DoesNotExist:
                # 2:15 pm on the 28th
                set_monthly_event("logistics.apps.logistics.schedule.reminder_to_submit_RRIRV",28,14,15)

    def parse (self, message):
        """Parse and annotate messages in the parse phase."""
        pass

    def _check_preconditions(self, message):
        """
        Handles base logic of whether this message should be processed.
        Returns a tuple, the first value is whether the operation should
        proceed with the normal handle phase, the second being the return n
        code. If the first argument is True, the value of the second argument 
        is not defined.
        """
        if not self._should_handle(message):
            return (False, False)
        if not hasattr(message,'logistics_contact'):
            message.respond(REGISTER_MESSAGE)
            return (False, True)
        if message.logistics_contact.supply_point is None:
            message.respond(NO_SUPPLY_POINT_MESSAGE)
            return (False, True)
        if not self._clean_message(message.text):
            message.respond(SOH_HELP_MESSAGE)
            return (False, True)
        return (True, None)
        
    def _send_error_response(self, message, stock_report):
        kwargs = {}
        if stock_report.product_stock:
            kwargs['stocks'] = ", ". join(stock_report.product_stock)
            error_message = 'You reported: %(stocks)s, but there were errors: %(err)s'
        else:
            error_message = '%(err)s'
        missing = stock_report.missing_products()
        if missing:
            kwargs['missing'] = ", ".join(missing)
            error_message = error_message + " Please report %(missing)s."
        kwargs['err'] = ", ".join(unicode(e) for e in stock_report.errors if not isinstance(e, UnknownCommodityCodeError))
        bad_codes = ", ".join(unicode(e) for e in stock_report.errors if isinstance(e, UnknownCommodityCodeError))
        kwargs['err'] = kwargs['err'] + "Unrecognized commodity codes: %(bad_codes)s." % {'bad_codes':bad_codes}
        error_message = (error_message + GET_HELP_MESSAGE).strip()
        message.respond(error_message, **kwargs)
    
    def _get_responses(self, stock_report):
        """
        Gets responses to a SOH message, in the form of a response to the 
        sender, a response to the supervisor, and kwargs to populate them.
        """
        response = ''
        super_response = ''
        stockouts = stock_report.stockouts()
        low_supply = stock_report.low_supply()
        over_supply = stock_report.over_supply()
        received = stock_report.received_products()
        missing_product_list = stock_report.missing_products()
        if stock_report.has_stockout:
            response = response + 'the following items are stocked out: %(stockouts)s. '
            super_response = "stockouts %(stockouts)s; "
        if low_supply:
            response = response + 'the following items need to be reordered: %(low_supply)s. '
            super_response = super_response + "below reorder level %(low_supply)s; "
        if stock_report.has_stockout or low_supply:
            response = response + 'Please place an order now. '
        if missing_product_list:
            if not response:
                response = response + 'thank you for reporting your stock on hand. '
            response = response + 'Still missing %(missing_stock)s. '
        if over_supply:
            super_response = super_response + "overstocked %(overstocked)s; "
            if not response:
                response = 'the following items are overstocked: %(overstocked)s. The district admin has been informed.'
        if not response:
            if received:
                response = 'thank you for reporting the commodities you have. You received %(received)s.'
            else:
                response = 'thank you for reporting the commodities you have in stock.'
        response = 'Dear %(name)s, ' + response.strip()
        if super_response:
            super_response = 'Dear %(admin_name)s, %(supply_point)s is experiencing the following problems: ' + super_response.strip().strip(';')
        kwargs = {  'low_supply': low_supply,
                    'stockouts': stockouts,
                    'missing_stock': ', '.join(missing_product_list),
                    'stocks': stock_report.all(),
                    'received': stock_report.received(),
                    'overstocked': over_supply,
                    'name': stock_report.message.contact.name,
                    'supply_point': stock_report.supply_point.name }
        return (response, super_response, kwargs)

    def _send_responses(self, message, stock_report):
        if stock_report.errors:
            self._send_error_response(message, stock_report)
        else:
            (response, super_response, kwargs) = self._get_responses(stock_report)
            message.respond(response, **kwargs)
            if super_response:
                message.logistics_contact.supply_point.report_to_supervisor\
                    (super_response, kwargs, exclude=[message.logistics_contact])

    def handle (self, message):
        """Add your main application logic in the handle phase."""
        should_proceed, return_code = self._check_preconditions(message)
        if not should_proceed:
            return return_code
        try:
            message.text = self._clean_message(message.text)
            stock_report = ProductReportsHelper(message.logistics_contact.supply_point, 
                                                STOCK_ON_HAND_REPORT_TYPE, message.logger_msg)
            stock_report.parse(message.text)
            stock_report.save()
            self._send_responses(message, stock_report)
            return True
            
        except Exception, e:
            if settings.DEBUG:
                # this error actually gets logged deep within rapidSMS
                message.respond(unicode(e))
            raise

    def default(self, message):
        """ There's probably a better way to do this, but for now,
        this is what the folks in the field want 
        """
        match = re.search("[0-9]", message.text)
        if match is not None:
            index = message.text.find(match.group(0))
            code = message.text[:index].strip()
            message.error("%s is not a recognized commodity code. " % code + 
                          "Please contact your DHIO for assistance." )
        elif settings.DEFAULT_RESPONSE is not None:
            message.error(settings.DEFAULT_RESPONSE,
                          project_name=settings.PROJECT_NAME)

    def cleanup (self, message):
        """Perform any clean up after all handlers have run in the
           cleanup phase."""
        pass

    def outgoing (self, message):
        """Handle outgoing message notifications."""
        pass

    def stop (self):
        """Perform global app cleanup when the application is stopped."""
        pass

    def _should_handle(self, message):
        """
        Tests whether this message is one which should go through the handle phase
        i.e. if it begins with soh or one of the product codes
        """
        keywords = [SOH_KEYWORD]
        keywords.extend(Product.objects.values_list('sms_code', flat=True).order_by('sms_code'))
        text = message.text.lower()
        for keyword in keywords:
            if text.startswith(keyword):
                return True
        return False

        
    def _clean_message(self, text):
        text = text.lower()
        if text.startswith(SOH_KEYWORD):
            return text.strip(SOH_KEYWORD)
        return text

