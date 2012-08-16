import re

from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

ATTRIBUTE_MODEL_NAME_PATTERN = re.compile('^[a-z0-9_]+$')


class ModelAttribute(models.Model):
    """
    Defines a simple name/value pair model that can be used with generic
    content type relationships to add any number of arbitrary properties to a
    model that inherits from BaseModel.

    Names should follow standard Python property naming conventions (and are
    enforced with a model validation method).  It will also be automatically
    lower-cased if it isn't already.

    Values can be anything as they are stored in a TextField.
    """

    name = models.CharField(
        max_length=255,
        help_text="""The name must be set to something that looks like a Python property (e.g., "my_property")."""
    )
    value = models.TextField(blank=True, default='')

    def clean(self):
        self.name = self.name.lower()

        if ATTRIBUTE_MODEL_NAME_PATTERN.match(self.name) is None:
            raise ValidationError(
                'The name must be in the format of a Python property (e.g., "my_property").'
            )


class AttributedModel(models.Model):
    """
    Defines a model that serves as the generic content type link between the
    ModelAttribute and the model it is related to.
    """

    attribute = models.ForeignKey(ModelAttribute)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    def __unicode__(self):
        return u'%s: %s' % (self.attribute.name, self.attribute.value)


class BaseModelManager(models.Manager):
    """
    Defines a model manager that accounts for arbitrary content type
    relationships associated with the model and sets up the necessary
    properties when doing a get of a single instance of the model.
    """

    def get(self, *args, **kwargs):
        return super(self, BaseModelManager).get(*args, **kwargs)

    def get_or_create(self, **kwargs):
        return super(self, BaseModelManager).get_or_create(**kwargs)

    def create(self, **kwargs):
        return super(self, BaseModelManager).create(**kwargs)


class BaseModel(models.Model):
    """
    Defines an abstract model built off of Django's Model class that
    provides some common fields that are useful on multiple models
    across multiple projects.
    """

    time_created = models.DateTimeField(auto_now_add=True, null=True)
    time_modified = models.DateTimeField(auto_now=True, null=True)
    last_modified_by = models.ForeignKey(
        User,
        related_name='%(app_label)s_%(class)s_related',
        null=True,
        blank=True
    )
    attributes = generic.GenericRelation(AttributedModel)

    objects = BaseModelManager()

    class Meta:
        abstract = True
