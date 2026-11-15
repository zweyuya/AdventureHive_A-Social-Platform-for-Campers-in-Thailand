from rest_framework import serializers

from .models import Notification, NotificationType as T, ReferenceType as R

MESSAGES = {
    T.RSVP_CONFIRMED: "You're confirmed for {trip}.",
    T.RSVP_WAITLISTED: "The trip {trip} is full — you're on the waitlist.",
    T.WAITLIST_PROMOTED: "A seat opened up — you're now confirmed for {trip}!",
    T.TRIP_CANCELLED: "{trip} has been cancelled.",
    T.TRIP_UPDATED: "{trip} has new dates or a new meeting point.",
    T.TRIP_REMINDER: "{trip} is over — please record who attended.",
    T.REVIEW_UNLOCKED: "Thanks for coming on {trip}! You can now review the campsite.",
    T.EMERGENCY_CONTACT_VIEWED: "{actor} (organizer of {trip}) opened the emergency contact "
                                "you shared.",
    T.APPEAL_ON_MY_TRIP: "{actor} appealed their no-show on {trip}. An admin will decide.",
    T.APPEAL_APPROVED: "Your no-show appeal for {trip} was approved. You can now review the campsite.",
    T.APPEAL_REJECTED: "Your no-show appeal for {trip} was not approved. See the note on the trip page.",
    T.RECAP_REMINDER: "How was {trip}? Share a few photos or a short recap in the trip posts.",
    T.TRIP_REPEATED: "{actor} is running {trip} again. You came last time, so you can join first.",
    T.TRIP_FLAGGED: "{trip} was flagged: attendees were marked attended without checking in.",
    T.REVIEW_ESCALATED: "A review of {location} has several open reports.",
    T.APPEAL_SUBMITTED: "{actor} appealed a no-show on {trip}. An admin needs to decide.",
    T.SUBMISSION_APPROVED: "Your campsite change for {location} was approved.",
    T.SUBMISSION_REJECTED: "Your campsite change for {location} needs changes.",
    T.ANSWER_POSTED: "Someone answered your question: {question}",
    T.FOLLOW: "You have a new follower.",
    T.LIKE: "{actor} reacted to your post.",
    T.REACTION: "{actor} reacted to your post.",
    T.COMMENT: "{actor} commented on your post.",
    T.REPLY: "{actor} replied to your comment.",
    T.GROUP_POST: "New post in your group.",
    T.POST_PENDING: "{actor} posted in {group} — waiting for your approval.",
    T.POST_APPROVED: "Your post in {group} was approved.",
    T.POST_REJECTED: "Your post in {group} wasn't approved. See the note from the admin.",
}


# Notifications for admins open the Django admin instead of a page in the app.
ADMIN_ROUTES = {
    T.TRIP_FLAGGED: "/admin/trips/trip/{}/change/",
    T.REVIEW_ESCALATED: "/admin/reviews/review/{}/change/",
    T.APPEAL_SUBMITTED: "/admin/trips/attendanceappeal/",
}


class NotificationSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()
    link = serializers.SerializerMethodField(help_text="Frontend route to open.")

    class Meta:
        model = Notification
        fields = ["id", "type", "message", "link", "reference_type", "reference_id",
                  "is_read", "created_at"]

    def _name(self, obj) -> str:
        names = self.context.get("names", {})
        return names.get((obj.reference_type, obj.reference_id), "a deleted item")

    def get_message(self, obj) -> str:
        template = MESSAGES.get(obj.type, "You have a new notification.")
        name = self._name(obj)
        actor = obj.actor.profile.display_name if obj.actor_id and hasattr(obj.actor, "profile") else "Someone"
        group = self.context.get("post_groups", {}).get(obj.reference_id, "the group") \
            if obj.reference_type == R.POST else "the group"
        return template.format(trip=name, location=name, question=name, actor=actor, group=group)

    def get_link(self, obj) -> str | None:
        if obj.type in ADMIN_ROUTES:
            return ADMIN_ROUTES[obj.type].format(obj.reference_id)
        routes = {R.TRIP: "/trips/{}", R.LOCATION: "/campsites/{}",
                  R.QUESTION: "/questions/{}", R.GROUP: "/groups/{}", R.USER: "/users/{}",
                  R.POST: "/posts/{}"}
        route = routes.get(obj.reference_type)
        return route.format(obj.reference_id) if route else None
