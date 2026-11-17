from urllib.parse import quote


class UPIService:
    """Generate UPI deep links for various payment apps."""

    APPS = {
        'phonepe': 'phonepe://pay',
        'paytm': 'paytmmp://pay',
        'googlepay': 'tez://upi/pay',
        'bhim': 'bhim://pay',
        'amazonpay': 'amazonpay://pay',
        'cred': 'credpay://pay',
        'generic': 'upi://pay',
    }

    @staticmethod
    def build_link(upi_id, name, amount, note='', app='generic'):
        base = UPIService.APPS.get(app.lower(), UPIService.APPS['generic'])
        params = (
            f"?pa={quote(upi_id)}"
            f"&pn={quote(name)}"
            f"&am={amount}"
            f"&cu=INR"
            f"&tn={quote(note)}"
        )
        return base + params

    @staticmethod
    def all_links(upi_id, name, amount, note=''):
        return {
            app: UPIService.build_link(upi_id, name, amount, note, app)
            for app in UPIService.APPS
        }