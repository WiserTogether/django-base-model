from django.contrib import admin
from django.contrib.contenttypes import generic

from django_base_model.models import ModelAttribute


class ModelAttributeInline(generic.GenericTabularInline):
    """
    Defines a ModelAttribute inline that can be used to add/modify/delete
    ModelAttribute objects associated with an object that inherits from
    BaseModel.
    """

    model = ModelAttribute
    extra = 0


class BaseModelAdmin(admin.ModelAdmin):
    """
    Defines a BaseModelAdmin based off of Django's ModelAdmin that supports any
    model built with the BaseModel class so that we're able to save the user
    information of whoever is modifying the object through the admin site.

    This requires that the model you are associating with the ModelAdmin object
    inherits from BaseModel.
    """

    exclude = ['last_modified_by', ]
    inlines = [ModelAttributeInline, ]

    readonly_fields = (
        'last_modified_by_name',
        'time_created',
        'time_modified'
    )

    def last_modified_by_name(self, obj):
        """
        Provides a means of displaying a Django User's name nicely in the
        Django admin for the last_modified_by property.
        """

        return obj.last_modified_by.get_full_name()
    last_modified_by_name.short_description = 'Last Modified By'

    def last_edited(self, obj):
        """
        Provides a means of displaying the time_modified value nicely in the
        Django admin.
        """

        return obj.time_modified.strftime('%m/%d/%Y %I:%M %p')
    last_edited.short_description = 'Last Edited'

    def created_on(self, obj):
        """
        Provides a means of displaying the time_created value nicely in the
        Django admin.
        """

        return obj.time_created.strftime('%m/%d/%Y %I:%M %p')
    created_on.short_description = 'Created On'

    def save_model(self, request, obj, form, change):
        """
        Overridden save_model method to add support for tracking who has last
        modified an object that inherits from BaseModel via the admin
        interface.
        """

        if hasattr(obj, 'last_modified_by') and hasattr(request, 'user'):
            obj.last_modified_by = request.user

        obj.save()

    def save_formset(self, request, form, formset, change):
        """
        Overridden save_formset method to add support for tracking who has last
        modified a batch of objects that inherits from BaseModel via the admin
        interface.
        """

        instances = formset.save(commit=False)

        for instance in instances:
            if hasattr(instance, 'last_modified_by') and hasattr(request, 'user'):
                instance.last_modified_by = request.user

            instance.save()

        formset.save_m2m()
