"""Initial public copy from SG_AllClean_Website_Brief_Completed.xlsx.

Applied once by the client-brief migration; subsequent CMS edits are preserved.
Prices live in each service's details, shared by every public service card.
"""

SETTINGS = {
    "company_name": "SG AllClean",
    "tagline": "Clean spaces. Clear minds. Better living.",
    "hero_title": "A clean space, ready for what comes next.",
    "hero_subtitle": "Condo, Airbnb turnover and small-office cleaning in Makati and BGC.",
    "intro_title": "Cleaning that fits your space and schedule.",
    "intro_body": "SG AllClean helps homeowners, hosts and offices arrange one-time and recurring cleaning. Choose a service, share your property details and receive a quote before we confirm your schedule.",
    "contact_phone": "+63 976 317 3177",
    "location": "Makati City, Metro Manila, Philippines",
    "coverage": "Makati and Bonifacio Global City (BGC), Taguig. Other Metro Manila areas by request.",
    "investment_note": "",
}

SERVICES = [
    dict(slug="residential-cleaning", title="Standard Condo Cleaning", highlight="One-time or recurring", sort_order=1,
         summary="Routine kitchen, bathroom, surfaces, floors and bins for normally maintained spaces.",
         details="Studio · up to 30 sqm\n₱1,299 · 1 cleaner · 3 hours\nRoutine kitchen, bathroom, surfaces, floors and bins.\n\n1BR · 31–50 sqm\n₱1,699 · 1 cleaner · 3 hours\nStandard cleaning including bedroom and common areas.\n\n2BR · 51–75 sqm\nFrom ₱2,499 · 2 cleaners · 3 hours\nStandard cleaning for two bedrooms and common areas."),
    dict(slug="move-in-move-out-deep-cleaning", title="Move-in/Move-out Deep Cleaning", highlight="A fresh start", sort_order=2,
         summary="Detailed cleaning for an empty property before moving in or after moving out.",
         details="Up to 50 sqm\nFrom ₱4,999 · 2 cleaners · 6 hours\n\nDetailed kitchen, bathroom, empty cabinets and accessible tracks. Cabinets must be empty.\n\nPlease share photos first so we can confirm the condition, tasks and quote."),
    dict(slug="airbnb-leasing-turnovers", title="Airbnb Guest-Ready Turnover", highlight="Between guest stays", sort_order=3,
         summary="A guest-ready checklist and a clear handover for your next arrival.",
         details="Studio · from ₱1,499\n1BR · from ₱1,899\n\nHost-provided linens, an essentials check and completion photos with owner/host approval.\n\nTiming is agreed after reviewing the unit, scope and guest schedule. The host supplies linens."),
    dict(slug="corporate-cleaning", title="Small Office Cleaning", highlight="One-time or weekly", sort_order=4,
         summary="Scheduled cleaning for small workplaces, with tasks agreed before each visit.",
         details="Up to 50 sqm\nFrom ₱1,999 · 4 hours per visit\n\nFour weekly visits\n₱7,200–₱7,600 per month for four scheduled visits.\n\nWe agree on the work areas, checklist, access and supplies before confirming your schedule."),
]

PAGES = {
    "about": ("Thoughtful care for everyday spaces.", "Led by experience in property management and Airbnb hosting.",
              "Experience in property management and Airbnb hosting shapes the service. We explain the cleaning process and set clear expectations before work begins.\n\nOur mission\nProvide dependable cleaning with agreed tasks, careful property handling and responsive communication.\n\nOur vision\nBecome a trusted cleaning partner for Metro Manila homes, hosts and workplaces."),
    "how-it-works": ("From your first inquiry to a clear handover.", "We agree on scope, price and schedule before confirming a booking.",
                     "Tell us about your space\nShare your service, approximate size, city/barangay and preferred date.\n\nShare photos if helpful\nPhotos help us assess deep cleaning or extra work. Only send photos you have permission to share.\n\nAgree on the details\nWe confirm scope, price, supplies, access and availability with you. Sending a form does not confirm a booking.\n\nFollow the checklist\nCleaners work through the agreed tasks, with any add-ons quoted before work begins.\n\nComplete the handover\nWe share a completion update and photos with owner/host approval."),
    "faq": ("A few things to know before we clean.", "Practical answers for homes, hosts and small offices.",
            "Where do you clean?\nMakati and BGC are our primary areas. Other Metro Manila locations are available by request.\n\nWhat is included?\nSee the service cards for inclusions and timing. We agree on the room-by-room checklist before your booking.\n\nAre the prices final?\nThese are starting prices for normally maintained spaces. Size, condition, access, extra time, parking, stains and add-ons may affect the final quote. Extra work is quoted first.\n\nDo you bring supplies?\nWe confirm which supplies are provided for each booking. Airbnb linens are supplied by the host.\n\nHow do I book?\nSend a quote request or message us. A booking is confirmed only after we agree on scope, price and schedule. There is no online payment or instant booking at launch.\n\nAre Airbnb completion photos provided?\nYes, with owner/host approval.\n\nCan I arrange regular cleaning?\nYes. Tell us your preferred frequency. The weekly office plan includes four scheduled visits."),
    "add-ons": ("Add-ons, quoted before we begin.", "Available with a cleaning visit; final scope and equipment availability are confirmed first.",
                "Refrigerator interior\nFrom ₱450 with a cleaning visit.\n\nAircon filter and exterior wipe\nFrom ₱200 per unit. No technical aircon servicing.\n\nCar cabin refresh\nFrom ₱699 for vacuum and wipe-down. Full detailing is quoted separately.\n\nUpholstery shampoo\n1-seater from ₱900; 2-seater/sofa bed from ₱1,400; 3-seater from ₱1,700. Equipment availability applies.\n\nHeavy stain treatment\nHard surface ₱300–₱600 per area. Fabric stains are quoted after photos; removal is not guaranteed.\n\nExcess rubbish\nFirst two extra bags ₱300; further bags ₱150 each. Off-site hauling is quoted separately.\n\nExtra bathroom, balcony or oven\nBathroom or balcony from ₱400 each; oven interior from ₱500."),
}

NAVIGATION = [("Home", "/", False), ("Services & Prices", "/services", False),
              ("How It Works", "/how-it-works", False), ("About", "/about", False),
              ("FAQ", "/faq", False), ("Request a Quote", "/contact", True)]

SNIPPETS = {
    "home.checklist_title": "Clear tasks. Careful handling. A proper handover.",
    "home.checklist_body": "We agree on a room-by-room checklist, confirm add-ons before work begins, and share a completion update. Guest-ready photos are shared only with owner or host permission.",
    "footer.badge": "Cleaning in Makati & BGC",
    "footer.body": "One-time and recurring cleaning for condos, Airbnb hosts and small offices. Scope, price and schedule agreed before booking.",
}
