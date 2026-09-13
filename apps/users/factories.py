import factory

from .models import Role, User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name = factory.Faker("name")
    role = Role.CUSTOMER

    # DjangoModelFactory's default create() calls User.objects.create(**kwargs), which
    # would store the password as plaintext — it has no idea a User needs set_password().
    # This hook runs after the instance exists and hashes the password properly instead.
    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "testpass123")
        if create:
            self.save()
