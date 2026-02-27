from django.urls import path

from . import views

app_name = "rides"

urlpatterns = [
    path("", views.driver_dashboard, name="index"),
    path("new/", views.create_ride, name="create_ride"),
    path("search/", views.rider_search, name="rider_search"),
    path("my-requests/", views.my_requests, name="my_requests"),
    path("my-requests/<int:req_pk>/cancel/", views.cancel_request, name="cancel_request"),
    path("my-requests/<int:req_pk>/", views.request_detail, name="request_detail"),
    path("profile/", views.my_profile, name="my_profile"),
    path("profile/<int:user_id>/", views.user_profile, name="user_profile"),
    path("ratings/", views.ratings_page, name="ratings"),
    path("ratings/submit/", views.submit_rating, name="submit_rating"),
    path("<int:pk>/", views.ride_detail, name="ride_detail"),
    path("<int:pk>/edit/", views.edit_ride, name="edit_ride"),
    path("<int:pk>/delete/", views.delete_ride, name="delete_ride"),
    path("<int:pk>/complete/", views.complete_ride, name="complete_ride"),
    path("<int:pk>/request/", views.request_ride, name="request_ride"),
    path("<int:pk>/requests/<int:req_pk>/accept/", views.accept_request, name="accept_request"),
    path("<int:pk>/requests/<int:req_pk>/reject/", views.reject_request, name="reject_request"),
    path("favorites/save/", views.save_favorite, name="save_favorite"),
    path("favorites/<int:pk>/delete/", views.delete_favorite, name="delete_favorite"),
]
