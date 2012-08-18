from operator import attrgetter

from django.contrib.contenttypes.generic import (
    GenericRelation,
    ReverseGenericRelatedObjectsDescriptor
)
from django.db import connection, router


class BaseGenericRelation(GenericRelation):
    """
    Defines an overridden GenericRelation class so that we're able to provide a
    few additional hooks for when we save a new ModelAttribute through the
    manager defined by Django's ContentType generics setup.

    Specifically, we want to be able to automatically add any new
    ModelAttribute created through those means as a new property on any object
    that inherits from BaseModel.
    """

    def contribute_to_class(self, cls, name):
        """
        Overridden contribute_to_class method so that we're able to setup a
        custom BaseReverseGenericRelatedObjectsDescriptor for use with a
        custom BaseGenericRelatedObjectManager when working with the manager of
        a GenericRelation.
        """

        super(BaseGenericRelation, self).contribute_to_class(cls, name)

        # Save a reference to which model this class is on for future use
        self.model = cls

        # Add the descriptor for the m2m relation
        setattr(
            cls,
            self.name,
            BaseReverseGenericRelatedObjectsDescriptor(self)
        )


class BaseReverseGenericRelatedObjectsDescriptor(ReverseGenericRelatedObjectsDescriptor):
    """
    Overridden ReverseGenericRelatedObjectsDescriptor object so that we can
    retrieve our custom BaseGenericRelatedObjectManager.
    """

    def __get__(self, instance, instance_type=None):
        """
        Override of the __get__ method to specifically retrieve the custom
        BaseGenericRelatedObjectManager.
        """

        if instance is None:
            return self

        # This import is done here to avoid circular import importing this
        # module.
        from django.contrib.contenttypes.models import ContentType

        # Dynamically create a class that subclasses the related model's
        # default manager.
        rel_model = self.field.rel.to
        superclass = rel_model._default_manager.__class__
        RelatedManager = create_generic_related_manager(superclass)

        qn = connection.ops.quote_name
        content_type = ContentType.objects.db_manager(
            instance._state.db
        ).get_for_model(instance)

        manager = RelatedManager(
            model=rel_model,
            instance=instance,
            symmetrical=(
                self.field.rel.symmetrical and instance.__class__ == rel_model
            ),
            source_col_name=qn(self.field.m2m_column_name()),
            target_col_name=qn(self.field.m2m_reverse_name()),
            content_type=content_type,
            content_type_field_name=self.field.content_type_field_name,
            object_id_field_name=self.field.object_id_field_name,
            prefetch_cache_name=self.field.attname,
        )

        return manager


def create_generic_related_manager(superclass):
    """
    This is a complete replacement of the create_generic_related_manager
    factory method in Django's ContentType generic setup.  We want to be able
    to return a custom manager object that has some enhancements related to the
    ModelAttribute model for objects that inherit from BaseModel.

    Factory function for a manager that subclasses 'superclass' (which is a
    Manager) and adds behavior for generic related objects.
    """

    class BaseGenericRelatedObjectManager(superclass):
        """
        Defines a custom manager for generic relations that is almost identical
        to Django's own GenericRelatedObjectManager.  This adds support for
        creating object properties out of a newly created model, included
        support for a get_or_create method.
        """

        def __init__(self, model=None, instance=None, symmetrical=None,
                     source_col_name=None, target_col_name=None,
                     content_type=None, content_type_field_name=None,
                     object_id_field_name=None, prefetch_cache_name=None):

            super(BaseGenericRelatedObjectManager, self).__init__()
            self.model = model
            self.content_type = content_type
            self.symmetrical = symmetrical
            self.instance = instance
            self.source_col_name = source_col_name
            self.target_col_name = target_col_name
            self.content_type_field_name = content_type_field_name
            self.object_id_field_name = object_id_field_name
            self.prefetch_cache_name = prefetch_cache_name
            self.pk_val = self.instance._get_pk_val()
            self.core_filters = {
                '%s__pk' % content_type_field_name: content_type.id,
                '%s__exact' % object_id_field_name: instance._get_pk_val(),
            }

        def get_query_set(self):
            try:
                return self.instance._prefetched_objects_cache[self.prefetch_cache_name]
            except (AttributeError, KeyError):
                db = self._db or router.db_for_read(self.model, instance=self.instance)
                return super(
                    BaseGenericRelatedObjectManager,
                    self
                ).get_query_set().using(db).filter(**self.core_filters)

        def get_prefetch_query_set(self, instances):
            db = self._db or router.db_for_read(
                self.model,
                instance=instances[0]
            )
            query = {
                '%s__pk' % self.content_type_field_name: self.content_type.id,
                '%s__in' % self.object_id_field_name:
                    set(obj._get_pk_val() for obj in instances)
                }
            qs = super(
                BaseGenericRelatedObjectManager,
                self
            ).get_query_set().using(db).filter(**query)

            return (qs,
                    attrgetter(self.object_id_field_name),
                    lambda obj: obj._get_pk_val(),
                    False,
                    self.prefetch_cache_name)

        def add(self, *objs):
            for obj in objs:
                if not isinstance(obj, self.model):
                    raise TypeError(
                        "'%s' instance expected" % self.model._meta.object_name
                    )

                setattr(obj, self.content_type_field_name, self.content_type)
                setattr(obj, self.object_id_field_name, self.pk_val)
                obj.save()
        add.alters_data = True

        def remove(self, *objs):
            db = router.db_for_write(self.model, instance=self.instance)

            for obj in objs:
                obj.delete(using=db)
        remove.alters_data = True

        def clear(self):
            db = router.db_for_write(self.model, instance=self.instance)

            for obj in self.all():
                obj.delete(using=db)
        clear.alters_data = True

        def get_or_create(self, content_object=None, **kwargs):
            """
            This get_or_create method takes in an optional argument of the
            object that this model is being created off of so that it's
            properties can be added to the related model automatically.

            The reason this optional argument is required in order to make this
            functionality work is due to the fact that a reference to the
            object in memory must be used in order for the property to be
            assigned to the correct instance of the object in memory.

            Keyword arguments:
            content_object -- the object that the property should be added to,
                              which must inherit from BaseModel.
            """

            kwargs[self.content_type_field_name] = self.content_type
            kwargs[self.object_id_field_name] = self.pk_val
            db = router.db_for_write(self.model, instance=self.instance)
            obj, created = super(
                BaseGenericRelatedObjectManager,
                self
            ).using(db).get_or_create(**kwargs)

            if created and content_object and hasattr(content_object, 'set_attribute'):
                content_object.set_attribute(obj.name, obj.value)

            return (obj, created)
        get_or_create.alters_data = True

        def create(self, content_object=None, **kwargs):
            """
            This create method takes in an optional argument of the object that
            this model is being created off of so that it's properties can be
            added to the related model automatically.

            The reason this optional argument is required in order to make this
            functionality work is due to the fact that a reference to the
            object in memory must be used in order for the property to be
            assigned to the correct instance of the object in memory.

            Keyword arguments:
            content_object -- the object that the property should be added to,
                              which must inherit from BaseModel.
            """

            kwargs[self.content_type_field_name] = self.content_type
            kwargs[self.object_id_field_name] = self.pk_val
            db = router.db_for_write(self.model, instance=self.instance)
            obj = super(
                BaseGenericRelatedObjectManager,
                self
            ).using(db).create(**kwargs)

            if content_object and hasattr(content_object, 'set_attribute'):
                content_object.set_attribute(obj.name, obj.value)

            return obj
        create.alters_data = True

    return BaseGenericRelatedObjectManager


try:
    # We need this to support South properly.
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], ["^django_base_model\.generic\.BaseGenericRelation"])
except:
    pass
