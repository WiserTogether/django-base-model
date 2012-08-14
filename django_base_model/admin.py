from django.contrib import admin


class BaseModelAdmin(admin.ModelAdmin):
    """
    Defines a BaseModelAdmin based off of Django's ModelAdmin that supports any
    model built with the BaseModel class so that we're able to save the user
    information of whoever is modifying the object through the admin site.

    This requires that the model you are associating with the ModelAdmin object
    inherits from BaseModel.
    """

    readonly_fields = (
        'last_modified_by_name',
        'time_created',
        'time_modified'
    )

    def last_modified_by_name(self, obj):
        return obj.last_modified_by.get_full_name()
    last_modified_by_name.short_description = 'Last Modified By'

    def save_model(self, request, obj, form, change):
        if hasattr(obj, 'last_modified_by') and hasattr(request, 'user'):
            obj.last_modified_by = request.user

        obj.save()

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for instance in instances:
            if hasattr(instance, 'last_modified_by') and hasattr(request, 'user'):
                instance.last_modified_by = request.user

            instance.save()

        formset.save_m2m()
