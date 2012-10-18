import re

from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from django_base_model import generic as base_generic

ATTRIBUTE_MODEL_NAME_PATTERN = re.compile('^[a-z0-9_]+$')


class ModelAttributeManager(models.Manager):
    """
    Defines a custom ModelManager that takes into account automatically adding
    new ModelAttributes as direct properties on objects that inherit from
    BaseModel.
    """

    def get_or_create(self, content_object=None, **kwargs):
        """
        Overwritten get_or_create method to support automatically adding the
        ModelAttribute as a direct property to the associated content object,
        if the object inherits from BaseModel.

        The reason this optional argument is required in order to make this
        functionality work is due to the fact that a reference to the object in
        memory must be used in order for the property to be assigned to the
        correct instance of the object in memory.

        Keyword arguments:
        content_object -- the object that the property should be added to,
                          which must inherit from BaseModel.
        """

        obj, created = super(
            ModelAttributeManager,
            self
        ).get_or_create(**kwargs)

        # Only reset the ModelAttribute association if the object was created.
        if created and content_object and hasattr(content_object, 'set_attribute'):
            content_object.set_attribute(obj.name, obj.value)

        return (obj, created)

    def create(self, content_object=None, **kwargs):
        """
        Overwritten create method to support automatically adding the
        ModelAttribute as a direct property to the associated content object,
        if the object inherits from BaseModel.

        The reason this optional argument is required in order to make this
        functionality work is due to the fact that a reference to the object in
        memory must be used in order for the property to be assigned to the
        correct instance of the object in memory.

        Keyword arguments:
        content_object -- the object that the property should be added to,
                          which must inherit from BaseModel.
        """

        obj = super(
            ModelAttributeManager,
            self
        ).create(**kwargs)

        if content_object and hasattr(content_object, 'set_attribute'):
            content_object.set_attribute(obj.name, obj.value)

        return obj


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
        help_text='The name must be set to something that looks like a Python property (e.g., "my_property").'
    )
    value = models.TextField(blank=True, default='')
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    objects = ModelAttributeManager()

    class Meta:
        unique_together = ('name', 'content_type', 'object_id')

    def __unicode__(self):
        return u'%s: %s' % (self.name, self.value)

    def clean(self):
        """
        Model clean method to validate the value of "name" before saving any
        changes to the model.  We only want valid names that could be turned
        easily into Python attributes on an object.
        """

        # Lower case the value of name automatically.
        self.name = self.name.lower()

        if ATTRIBUTE_MODEL_NAME_PATTERN.match(self.name) is None:
            raise ValidationError(
                '"name" must be in the format of a Python object property (e.g., "my_property").'
            )

    def save(self, *args, **kwargs):
        """
        Override the save method so that we ensure we're saving the model
        fields properly.  By calling the full_clean method, anything that is
        not correct will cause a ValidationError to be raised.
        """

        self.full_clean()
        return super(ModelAttribute, self).save(*args, **kwargs)


class BaseModelManager(models.Manager):
    """
    Defines a model manager that accounts for arbitrary content type
    relationships associated with the model and sets up the necessary
    properties when doing a get of a single instance of the model.
    """

    def get(self, *args, **kwargs):
        """
        Overwritten get method to support adding ModelAttribute associations
        automatically when retrieving an object that inherits from BaseModel.
        """

        obj = super(BaseModelManager, self).get(*args, **kwargs)
        obj.set_attributes()

        return obj

    def get_or_create(self, attributes=None, attribute_names=None, **kwargs):
        """
        Overwritten get_or_create method to support creating ModelAttribute
        associations automatically when creating an object that inherits from
        BaseModel.  When retrieving the object, any existing ModelAttribute
        associations will be tied directly to the object as properties.

        Keyword arguments:
        attributes -- a dictionary of name/value pairs.
        attribute_names -- a list of attribute names.
        """

        obj, created = super(BaseModelManager, self).get_or_create(**kwargs)

        # Only create the attributes if the object was created.
        if created:
            obj.create_attributes(
                attributes=attributes,
                attribute_names=attribute_names
            )

        return (obj, created)

    def create(self, attributes=None, attribute_names=None, **kwargs):
        """
        Overwritten create method to support creating ModelAttribute
        associations automatically when creating an object that inherits from
        BaseModel and associating the attributes with the object directly as
        properties on the object.

        Keyword arguments:
        attributes -- a dictionary of name/value pairs.
        attribute_names -- a list of attribute names.
        """

        obj = super(BaseModelManager, self).create(**kwargs)

        obj.create_attributes(
            attributes=attributes,
            attribute_names=attribute_names
        )

        return obj

    def all_with_attributes(self, *args, **kwargs):
        """
        An extra all method to support adding ModelAttribute associations
        to each object in the QuerySet automatically when filtering on an
        object that inherits from BaseModel.

        This is a separate method as it may be expensive to run due to the
        evaluation of the query set being returned.
        """

        query_set = super(BaseModelManager, self).all(*args, **kwargs)

        for obj in query_set:
            obj.set_attributes()

        return query_set

    def filter_with_attributes(self, *args, **kwargs):
        """
        An extra filter method to support adding ModelAttribute associations
        to each object in the QuerySet automatically when filtering on an
        object that inherits from BaseModel.

        This is a separate method as it may be expensive to run due to the
        evaluation of the query set being returned.
        """

        query_set = super(BaseModelManager, self).filter(*args, **kwargs)

        for obj in query_set:
            obj.set_attributes()

        return query_set

    def exclude_with_attributes(self, *args, **kwargs):
        """
        An extra exclude method to support adding ModelAttribute associations
        to each object in the QuerySet automatically when filtering by
        exclusion on an object that inherits from BaseModel.

        This is a separate method as it may be expensive to run due to the
        evaluation of the query set being returned.
        """

        query_set = super(BaseModelManager, self).exclude(*args, **kwargs)

        for obj in query_set:
            obj.set_attributes()

        return query_set


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
    attributes = base_generic.BaseGenericRelation(ModelAttribute)

    objects = BaseModelManager()

    class Meta:
        abstract = True

    def get_attributes_as_dict(self):
        """
        Retrieves all attributes associated with the model that inherits from
        this BaseModel class and returns them as a dictionary.
        """

        return {name: value for name, value in self.attributes.values_list('name', 'value')}

    def set_attribute(self, name, value, overwrite=False):
        """
        Sets a single attribute, usually when a new ModelAttribute object is
        created.

        Keyword arguments:
        name -- The name of the attribute (from the ModelAttribute object).
        value -- the value of the attribute (from the ModelAttribute object).
        overwrite -- A boolean flag that will set a property without regard for
                     any existing value that may already be set.
        """

        if overwrite or not hasattr(self, name):
            setattr(self, name, value)

    def set_attributes(self, overwrite=False):
        """
        Loops through all associated ModelAttribute objects and sets them up as
        properties on the object directly.

        Keyword arguments:
        overwrite -- A boolean flag that will set a property without regard for
                     any existing value that may already be set.
        """

        for attribute in self.attributes.all():
            if attribute.name:
                if overwrite or not hasattr(self, attribute.name):
                    setattr(self, attribute.name, attribute.value)

    def create_attributes(self, **kwargs):
        """
        Given a dictionary or list of attributes, creates a series of
        ModelAttribute objects associated with the object and then
        automatically sets them as properties on the object.

        If attributes is present in the kwargs, attribute_names will be
        ignored.

        Keyword arguments:
        attributes -- a dictionary of name/value pairs.
        attribute_names -- a list of attribute names.
        """

        attributes = kwargs.get('attributes', None)
        attribute_names = kwargs.get('attribute_names', None)

        if attributes:
            for name, value in attributes.items():
                self.attributes.create(self, name=name, value=value)
        elif attribute_names:
            for name in attribute_names:
                self.attributes.create(self, name=name)

    def update_attributes(self, **kwargs):
        """
        Given a dictionary of attributes, updates all of the ModelAttribute
        objects associated with the object with the new values provided.

        If create is present in the kwargs and True, any attribute that is not
        found will also be created.

        Keyword arguments:
        attributes -- a dictionary of name/value pairs.
        create --  a boolean indicating whether or not attributes that don't
                   exist should be created.
        """

        attributes = kwargs.get('attributes', None)
        create = kwargs.get('create', False)

        if attributes:
            for name, value in attributes.items():
                try:
                    model_attribute = self.attributes.get(name=name)
                except ModelAttribute.DoesNotExist:
                    if create:
                        self.attributes.create(self, name=name, value=value)
                    else:
                        continue
                else:
                    model_attribute.value = value
                    model_attribute.save()
                    self.set_attribute(name=name, value=value, overwrite=True)
