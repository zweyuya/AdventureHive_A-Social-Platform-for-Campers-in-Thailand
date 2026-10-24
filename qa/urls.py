from rest_framework.routers import DefaultRouter

from .views import AnswerViewSet, QuestionViewSet

router = DefaultRouter(trailing_slash=True)
router.register("questions", QuestionViewSet, basename="question")
router.register("answers", AnswerViewSet, basename="answer")

urlpatterns = router.urls
