odoo.define('report_customization.account_report', function (require) {
"use strict";
var rpc = require('web.rpc');

var currencyaccountReportsWidget = require('account_reports.account_report');

currencyaccountReportsWidget.include({

    render_searchview_buttons: function(val) {
        var self = this;
        this._super(...arguments)
        this.$searchview_buttons.find('.js_currency_selector').click(function (event) {
            var option_value = $(this).data('id');
            self.report_options.selected_currency_id=option_value;
            self.reload();
        });
    },

});
});
