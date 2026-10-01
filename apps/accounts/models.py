from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    OPERATOR = "OPERATOR", "Operador PNAE"
    MANAGER = "MANAGER", "Gestor"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuário precisa de is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuário precisa de is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Usuário da equipe. Login por e-mail.

    `campus` nulo indica administrador global (acesso a todos os campus).
    `can_*` são permissões individuais adicionais (RN-05 / perfil Gestor é
    somente leitura no MVP).
    """

    email = models.EmailField("e-mail", unique=True)
    name = models.CharField("nome", max_length=150)
    campus = models.ForeignKey(
        "campus.Campus",
        on_delete=models.PROTECT,
        related_name="users",
        verbose_name="campus",
        null=True,
        blank=True,
    )
    role = models.CharField(
        "perfil", max_length=20, choices=UserRole.choices, default=UserRole.OPERATOR
    )
    can_authorize_extras = models.BooleanField("pode autorizar excedente", default=False)
    can_reverse_deliveries = models.BooleanField("pode estornar entrega", default=False)
    is_active = models.BooleanField("ativo", default=True)
    is_staff = models.BooleanField("acesso ao admin", default=False)
    date_joined = models.DateTimeField("criado em", default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["name"]

    def __str__(self):
        return self.name or self.email

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name.split(" ")[0] if self.name else self.email
