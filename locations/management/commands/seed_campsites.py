"""
Seed 15 real Thai campsites and the authorities that manage them.

Idempotent: run it as often as you like; rows are matched by name.

IMPORTANT — data quality:
  * Names, provinces and managing authorities are real.
  * Coordinates are APPROXIMATE (good enough for a map pin, not for navigation).
  * Facilities are a best-effort starting point.
  * permit_status is 'unknown' and permit_info_verified_at is empty on purpose:
    nothing here has been verified with the park offices yet. Verify before
    relying on it, then update permit_info_source / permit_info_verified_at.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from locations.models import Authority, AuthorityType, Location, LocationStatus
from locations.services import _record_version

DNP_BOOKING = "https://reservation.dnp.go.th"

AUTHORITIES = {
    "khao_yai": ("Khao Yai National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
    "doi_inthanon": ("Doi Inthanon National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
    "chiang_dao": ("Doi Luang Chiang Dao Wildlife Sanctuary Office", AuthorityType.OTHER, ""),
    "phu_kradueng": ("Phu Kradueng National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
    "phu_chi_fa": ("Phu Chi Fa Forest Park Office", AuthorityType.FOREST_PARK, ""),
    "si_nan": ("Si Nan National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
    "pang_ung": ("Pang Tong Royal Development Project (Pang Ung)", AuthorityType.OTHER, ""),
    "kaeng_krachan": ("Kaeng Krachan National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
    "erawan": ("Erawan National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
    "sam_roi_yot": ("Khao Sam Roi Yot National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
    "tarutao": ("Mu Ko Tarutao National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
    "similan": ("Mu Ko Similan National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
    "pha_taem": ("Pha Taem National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
    "phu_ruea": ("Phu Ruea National Park Office", AuthorityType.NATIONAL_PARK, DNP_BOOKING),
}

# name, province, lat, lng, category, authority, water, restrooms, terrain, description
CAMPSITES = [
    ("Lam Ta Khong Campground", "Nakhon Ratchasima", 14.430, 101.385, "campground", "khao_yai",
     True, True, "Grassland by a stream",
     "Large campground in Khao Yai near the visitor centre; deer often graze nearby."),
    ("Pha Kluai Mai Campground", "Nakhon Ratchasima", 14.435, 101.405, "campground", "khao_yai",
     True, True, "Forest clearing",
     "Shaded campground in Khao Yai, close to the Haew Suwat waterfall trail."),
    ("Doi Inthanon Park HQ Campground", "Chiang Mai", 18.535, 98.520, "campground", "doi_inthanon",
     True, True, "Highland pine forest",
     "Cool-weather camping below Thailand's highest peak; cold nights in winter."),
    ("Den Ya Kat Camp, Doi Luang Chiang Dao", "Chiang Mai", 19.400, 98.890, "backcountry",
     "chiang_dao", False, True, "Limestone mountain ridge",
     "Base camp for the Doi Luang Chiang Dao summit trek; access is seasonal."),
    ("Phu Kradueng Summit Campground", "Loei", 16.860, 101.800, "campground", "phu_kradueng",
     True, True, "Sandstone plateau",
     "Plateau-top campground reached by a steep day hike; tents can be rented on top."),
    ("Phu Chi Fa Campground", "Chiang Rai", 19.850, 100.450, "campsite", "phu_chi_fa",
     False, True, "Mountain ridge",
     "Ridge-line camping near the famous sea-of-mist sunrise viewpoint."),
    ("Doi Samer Dao Campground", "Nan", 18.400, 100.770, "campground", "si_nan",
     False, True, "Grassy hilltop",
     "Open hilltop campground in Si Nan National Park with wide sunset views."),
    ("Pang Ung Reservoir Campsite", "Mae Hong Son", 19.500, 97.920, "campsite", "pang_ung",
     True, True, "Pine forest by a reservoir",
     "Misty lake surrounded by pine trees; very cold in December–January."),
    ("Ban Krang Campground", "Phetchaburi", 12.800, 99.470, "campground", "kaeng_krachan",
     True, True, "Riverside forest",
     "Riverside campground in Kaeng Krachan; popular for birdwatching and butterflies."),
    ("Erawan Waterfall Campground", "Kanchanaburi", 14.370, 99.140, "campground", "erawan",
     True, True, "Forest near waterfalls",
     "Campground near the seven-tier Erawan waterfall."),
    ("Sam Phraya Beach Campground", "Prachuap Khiri Khan", 12.200, 99.950, "campground",
     "sam_roi_yot", True, True, "Beach and casuarina trees",
     "Beachside camping under casuarina trees in Khao Sam Roi Yot National Park."),
    ("Ao Phante Campground, Ko Tarutao", "Satun", 6.700, 99.645, "campground", "tarutao",
     True, True, "Island beach",
     "Island campground near the Ko Tarutao park office; reached by ferry."),
    ("Ko Miang Campground, Similan Islands", "Phang Nga", 8.570, 97.640, "campground", "similan",
     True, True, "Island beach",
     "Island campsite in the Similan Islands; the park closes in the monsoon season."),
    ("Pha Taem Campground", "Ubon Ratchathani", 15.405, 105.505, "campground", "pha_taem",
     True, True, "Sandstone cliff top",
     "Cliff-top camping above the Mekong, near prehistoric rock paintings."),
    ("Phu Ruea Campground", "Loei", 17.500, 101.350, "campground", "phu_ruea",
     True, True, "Highland grassland",
     "Highland campground known for very cool winter temperatures."),
]


class Command(BaseCommand):
    help = "Create/update 15 published Thai campsites with authorities (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        authorities = {}
        for key, (name, a_type, booking) in AUTHORITIES.items():
            authorities[key], _ = Authority.objects.update_or_create(
                name=name, defaults={"authority_type": a_type, "booking_url": booking},
            )

        created = updated = 0
        for (name, province, lat, lng, category, auth_key, water, restrooms,
             terrain, description) in CAMPSITES:
            location, is_new = Location.objects.update_or_create(
                name=name,
                defaults={
                    "province": province, "latitude": lat, "longitude": lng,
                    "category": category, "authority": authorities[auth_key],
                    "has_water_source": water, "has_restrooms": restrooms,
                    "fire_pit_allowed": False,  # conservative default; most parks restrict fires
                    "terrain_type": terrain, "description": description,
                    "permit_status": "unknown",
                    "permit_details": "Not yet verified. Check with the managing authority "
                                      "before your trip.",
                    "permit_info_source": "Seed data (unverified)",
                    "status": LocationStatus.PUBLISHED,
                    "created_by": None,
                },
            )
            if is_new:
                _record_version(location, None, None, "Imported from seed data")
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Campsites: {created} created, {updated} updated "
            f"({Location.objects.published().count()} published in total)."
        ))
