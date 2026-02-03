from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse
from django.utils.timezone import now
from django.conf import settings
from django.contrib.auth.models import User

import uuid
import json
import os

from .models import Event, Booking, Payment, CheckinLog, Profile
from .forms import SignUpForm, EventForm
from core.utils import generate_qr_code

# Home
def home(request):
    return render(request, 'home.html')


# Event list and detail views
def event_list(request):
    events = Event.objects.all()
    return render(request, 'event_list.html', {'events': events})

def event_detail(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    return render(request, 'event_detail.html', {'event': event})


from django.contrib.auth.decorators import login_required

@login_required
def booking_list(request):
    bookings = Booking.objects.filter(user=request.user)
    return render(request, 'bookings.html', {'bookings': bookings})


# API: All Events
def api_event_list(request):
    events = Event.objects.all().values('id', 'name', 'description', 'location', 'date', 'capacity')
    return JsonResponse(list(events), safe=False)

# API: Single Event
def api_event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    data = {
        'id': event.id,
        'name': event.name,
        'description': event.description,
        'location': event.location,
        'date': event.date,
        'capacity': event.capacity,
    }
    return JsonResponse(data)


from django.core.mail import send_mail
from django.conf import settings

def book_ticket(request, event_id):
    if request.method == 'POST':
        try:
            user = request.user
            event = Event.objects.get(pk=event_id)
            ticket_id = str(uuid.uuid4())[:8]

            booking = Booking.objects.create(
                user=user,
                event=event,
                status='PENDING',
                ticket_id=ticket_id
            )

            # ✅ Generate QR code
            qr_filename = f'{booking.ticket_id}.png'
            booking.qr_code_path = generate_qr_code(data=booking.ticket_id, filename=qr_filename)
            booking.save()

            # ✅ Email sending
            if user.email:
                print("User email:", user.email)
                print("Preparing to send confirmation email...")

                qr_url = request.build_absolute_uri('/media/' + booking.qr_code_path)

                send_mail(
                    subject=f"🎫 Your Ticket for {event.title}",
                    message=f"""Hi {user.username},

Your ticket booking was successful!

Event: {event.title}
Ticket ID: {ticket_id}
Status: {booking.status}

QR Code: {qr_url}

Thank you for using QrEntry!""",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

                print("✅ Email sent successfully to", user.email)

            return redirect('booking_success', booking_id=booking.id)

        except Event.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Event not found'})

    return JsonResponse({'success': False, 'error': 'Invalid request'})



# ✅ Success page
def booking_success(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    return render(request, 'booking_success.html', {'booking': booking})


# ✅ Signup View with Password Confirmation + Role
def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        role = request.POST.get('role')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'signup.html', {'form': form})

        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.set_password(password)
            user.save()

            Profile.objects.create(user=user, role=role)
            messages.success(request, "Signup successful!")
            return redirect('login')
        else:
            messages.error(request, "Signup failed. Please check the form.")
    else:
        form = SignUpForm()

    return render(request, 'signup.html', {'form': form})


# ✅ Login View
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('event_list')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})

    return render(request, 'login.html')


# ✅ Logout View
def logout_view(request):
    logout(request)
    return redirect('login')


# ✅ Create Event (organiser only)
@login_required
def create_event(request):
    if request.user.profile.role != 'organiser':
        return redirect('event_list')

    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.save()
            return redirect('event_list')
    else:
        form = EventForm()

    return render(request, 'create_event.html', {'form': form})


# ✅ Download QR Code
def download_qr_code(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.qr_code_path:
        file_path = os.path.join(settings.MEDIA_ROOT, booking.qr_code_path)
        if os.path.exists(file_path):
            return FileResponse(open(file_path, 'rb'), content_type='image/png')
        else:
            return JsonResponse({'success': False, 'error': 'QR file not found'})
    return JsonResponse({'success': False, 'error': 'QR not assigned'})


# ✅ Mark Attendance (API)
@csrf_exempt
def mark_attendance(request, ticket_id):
    try:
        booking = Booking.objects.get(ticket_id=ticket_id)
        booking.status = 'ATTENDED'
        booking.save()
        return JsonResponse({'success': True, 'message': 'Attendance marked'})
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ticket not found'})


# ✅ Scan Attendance (HTML page)
@csrf_exempt
def scan_attendance(request):
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        try:
            booking = Booking.objects.get(ticket_id=ticket_id)
            if booking.status != 'ATTENDED':
                booking.status = 'ATTENDED'
                booking.save()
                return render(request, 'scan_attendance.html', {'status': 'success', 'ticket_id': ticket_id})
            else:
                return render(request, 'scan_attendance.html', {'status': 'fail', 'ticket_id': ticket_id})
        except Booking.DoesNotExist:
            return render(request, 'scan_attendance.html', {'status': 'fail', 'ticket_id': ticket_id})
    
    return render(request, 'scan_attendance.html')


# ✅ Scan QR Camera Page
def scan_qr_camera(request):
    return render(request, 'scan_qr.html')


# ✅ Fake Payment for Dev Testing
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, redirect, render
from django.core.mail import EmailMessage
from django.conf import settings
from .models import Event, Booking
from .utils import generate_qr_code  # Update this import if needed
import uuid
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

@csrf_exempt
@login_required
def fake_payment(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        user = request.user
        ticket_id = str(uuid.uuid4())[:8]

        # ✅ Create booking
        booking = Booking.objects.create(
            user=user,
            event=event,
            ticket_id=ticket_id,
            status='PENDING'
        )

        # ✅ Generate QR code image
        qr_filename = f'{ticket_id}.png'
        booking.qr_code_path = generate_qr_code(data=ticket_id, filename=qr_filename)
        booking.save()

        # ✅ Send email with PDF ticket
        if user.email:
            print("Preparing to send email with PDF...")

            # Step 1: Generate the PDF
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)

            # Ticket text
            p.setFont("Helvetica-Bold", 14)
            p.drawString(100, 750, "🎟️ QrEntry Ticket Confirmation")
            p.setFont("Helvetica", 12)
            p.drawString(100, 720, f"Name: {user.username}")
            p.drawString(100, 700, f"Event: {event.name}")
            p.drawString(100, 680, f"Ticket ID: {ticket_id}")
            p.drawString(100, 660, f"Status: {booking.status}")
            p.drawString(100, 640, "Please show this ticket at entry.")

            # Step 2: Add QR code image to PDF
            qr_path = os.path.join(settings.MEDIA_ROOT, booking.qr_code_path)
            if os.path.exists(qr_path):
                p.drawImage(ImageReader(qr_path), 100, 500, width=150, height=150)

            p.showPage()
            p.save()
            buffer.seek(0)

            # Step 3: Create email
            email = EmailMessage(
                subject=f"🎫 Your Ticket for {event.name}",
                body=f"""Hi {user.username},

Your ticket booking was successful!

Please find your ticket attached as a PDF.

Event: {event.name}
Ticket ID: {ticket_id}
Status: {booking.status}

Show the QR code at the event entry.

Thank you for using QrEntry!""",
                from_email=settings.EMAIL_HOST_USER,
                to=[user.email],
            )

            # Step 4: Attach the PDF
            email.attach(f"{ticket_id}_ticket.pdf", buffer.read(), "application/pdf")
            email.send()

            print("✅ Email with PDF sent to:", user.email)

        # ✅ Redirect to booking success page
        return redirect('booking_success', booking_id=booking.id)

    return render(request, 'payment_page.html', {'event': event})



# ✅ Payment Webhook Handler (Simulated)
@csrf_exempt
def payment_webhook(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ticket_id = data.get('ticket_id')
            payment_status = data.get('status')

            booking = Booking.objects.get(ticket_id=ticket_id)
            if payment_status == 'SUCCESS':
                booking.status = 'CONFIRMED'
                booking.save()

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


# ✅ Attendance HTML form view
@csrf_exempt
def attendance_form(request):
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        try:
            booking = Booking.objects.get(ticket_id=ticket_id)
            booking.status = 'ATTENDED'
            booking.save()
            return render(request, 'attendance.html', {'success': True, 'message': f"Attendance marked for {ticket_id}"})
        except Booking.DoesNotExist:
            return render(request, 'attendance.html', {'error': True, 'message': "Ticket not found"})
    return render(request, 'attendance.html')


from django.contrib.auth.models import User

def create_admin_user():
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@example.com", "admin123")
        print("Superuser created")

create_admin_user()


@login_required
def organizer_bookings(request):
    bookings = Booking.objects.filter(event__organizer=request.user)
    return render(request, 'organizer_bookings.html', {'bookings': bookings})



@login_required
def payment_page(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    user = request.user

    # Create a ticket booking
    ticket_id = str(uuid.uuid4())[:8]
    booking = Booking.objects.create(
        user=user,
        event=event,
        ticket_id=ticket_id,
        status='PENDING'
    )

    # Generate QR Code with UPI link
    upi_id = event.upi_id
    amount = event.price
    upi_link = f"upi://pay?pa={upi_id}&pn={event.name}&am={amount}&cu=INR"

    qr_filename = f"{ticket_id}.png"
    qr_path = generate_qr_code(upi_link, qr_filename)
    booking.qr_code_path = qr_path
    booking.save()

    return render(request, 'payment_page.html', {
        'event': event,
        'booking': booking,
        'upi_link': upi_link
    })
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import os

@login_required
def payment_success(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if request.method == "POST" and request.FILES.get('payment_screenshot'):
        uploaded_file = request.FILES['payment_screenshot']

        # Store in 'payment_ss/' directory inside media
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'payment_ss'), base_url='/media/payment_ss/')
        filename = fs.save(uploaded_file.name, uploaded_file)
        file_url = fs.url(filename)

        # Save relative path to model field
        booking.payment_screenshot.name = 'payment_ss/' + filename
        booking.status = 'Success'  # Or 'Pending' if you want manual verification
        booking.save()

        return redirect('booking_list')
    
    return render(request, 'payment_success.html', {'booking': booking})


from django.contrib import messages

@login_required
def create_event(request):
    if request.user.profile.role != 'organiser':
        return redirect('event_list')

    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.save()
            form.save()
            messages.success(request, "✅ Event created successfully!")
            return redirect('event_list')
        else:
            messages.error(request, "❌ Please correct the errors below.")
    else:
        form = EventForm()

    return render(request, 'create_event.html', {'form': form})

from django.shortcuts import render, redirect
from .forms import ParticipantForm

def register_participant(request):
    if request.method == 'POST':
        form = ParticipantForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('registration_success')
    else:
        form = ParticipantForm()
    return render(request, 'register_participant.html', {'form': form})
