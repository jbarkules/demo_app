class UsersController < ApplicationController
  allow_unauthenticated_access only: %i[ index show ]

  def index
    @role = params[:role].presence_in(%w[developer client]) || "developer"
    @users = User.where(role: User.roles[@role]).order(:display_name)
    @users = @users.where("display_name LIKE :q OR company_name LIKE :q OR location LIKE :q",
                          q: "%#{params[:q]}%") if params[:q].present?
  end

  def show
    @user = User.find(params[:id])
    @reviews = @user.reviews_received.recent.includes(:reviewer)
  end
end
