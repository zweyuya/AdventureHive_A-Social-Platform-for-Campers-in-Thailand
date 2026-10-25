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
        routes = {R.TRIP: "/trips/{}", R.LOCATION: "/campsites/{}",
                  R.QUESTION: "/questions/{}", R.GROUP: "/groups/{}", R.USER: "/users/{}",
                  R.POST: "/posts/{}"}
        route = routes.get(obj.reference_type)
        return route.format(obj.reference_id) if route else None
