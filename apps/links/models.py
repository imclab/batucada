import logging

from django.db import models
from django.db.models.signals import post_save, post_delete

from django_push.subscriber.models import Subscription
from django_push.subscriber.signals import updated

from links import tasks

log = logging.getLogger(__name__)


class Link(models.Model):
    """
    A link that can be added to a project or user. Links that have an Atom or
    RSS feed will be subscribed to using the declared hub or SuperFeedrs.
    """
    name = models.CharField(max_length=100)
    url = models.URLField(max_length=1023)
    project = models.ForeignKey('projects.Project', null=True)
    user = models.ForeignKey('users.UserProfile', null=True)
    subscription = models.ForeignKey(Subscription, null=True)
    broadcast = False


def link_create_handler(sender, **kwargs):
    """Check for a feed and subscribe to it if it exists."""
    link = kwargs.get('instance', None)
    created = kwargs.get('created', False)

    if not link.broadcast:
        return

    if not created or not isinstance(link, Link):
        return

    tasks.SubscribeToFeed.apply_async(args=(link,))
post_save.connect(link_create_handler, sender=Link)


def link_delete_handler(sender, **kwargs):
    """If the link had an associated feed subscription, unsubscribe."""
    link = kwargs.get('instance', None)

    if not isinstance(link, Link):
        return

    if not link.subscription:
        return

    tasks.UnsubscribeFromFeed.apply_async(args=(link,))
post_delete.connect(link_delete_handler, sender=Link)


def listener(notification, **kwargs):
    """
    Create activity entries when we receive notifications of
    feed updates from a hub.
    """
    sender = kwargs.get('sender', None)
    if not sender:
        return
    try:
        tasks.HandleNotification.apply_async(args=(notification, sender))
    except:
        log.warn("Unprocessable notification: %s" % (notification,))
updated.connect(listener)
