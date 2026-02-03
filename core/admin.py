from django.contrib import admin
from .models import Event, Booking, Payment, CheckinLog
from django.utils.safestring import mark_safe



from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')



@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
       list_display = ['name', 'date', 'organizer', 'location', 'capacity']
      
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'status', 'ticket_id', 'payment_screenshot_preview')

    readonly_fields = ('payment_screenshot_preview',)

    def payment_screenshot_preview(self, obj):
        if hasattr(obj, 'payment') and obj.payment.payment_screenshot:
            return mark_safe(f'<img src="{obj.payment.payment_screenshot.url}" width="150" />')
        return "No Screenshot"
    
    payment_screenshot_preview.short_description = "Payment Screenshot"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'booking', 'amount', 'status', 'payment_time')

@admin.register(CheckinLog)
class CheckinLogAdmin(admin.ModelAdmin):
    list_display = ('booking', 'scanned_by', 'checkin_time')
